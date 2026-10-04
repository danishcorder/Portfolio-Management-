from fastapi import FastAPI,Depends,HTTPException
from fastapi.security import HTTPAuthorizationCredentials,HTTPBearer
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel,Field
from pathlib import Path
from datetime import datetime
import json
from .db import Base,engine,get_db
from .models import *
from .services.finance import *
from .services.evaluation import compliance,score,narrative
from .services.auth import hash_password,verify_password,new_token,token_hash,token_expiry
from .services.asset_master import PSX_STOCKS,correlation
from .services.market_engine import response,generic_stock_response
from .services.activity_catalog import MANDATES,SCENARIOS
Base.metadata.create_all(engine)
app=FastAPI(title='Portfolio Market Simulation',version='1.0')
bearer=HTTPBearer(auto_error=False)
STATIC=Path(__file__).parent/'static'; app.mount('/static',StaticFiles(directory=STATIC),name='static')
@app.get('/')
def home(): return FileResponse(STATIC/'index.html')
class InvestorIn(BaseModel): name:str=Field(min_length=1,max_length=120); capital:float=Field(gt=0); risk_profile:str='Moderate'; horizon:str='1 year'; target_return:float=Field(default=.12,ge=-1,le=10); max_risk:float=Field(default=.20,ge=0,le=5); max_equity:float=Field(default=.60,ge=0,le=1); min_liquidity:float=Field(default=.05,ge=0,le=1)
class PortfolioIn(BaseModel): investor_id:int; team_name:str=Field(min_length=1,max_length=120)
class TradeIn(BaseModel): asset_id:int|None=None; action:str; quantity:float=Field(default=0,ge=0); reason:str=Field(default='',max_length=1000); market_type:str='SECONDARY'; expected_outcome:str|None=Field(default=None,max_length=1000); main_risk:str|None=Field(default=None,max_length=1000); confidence_level:int|None=Field(default=None,ge=1,le=5); mandate_connection:str|None=Field(default=None,max_length=1000)
class EventIn(BaseModel): name:str=Field(min_length=1,max_length=160); event_type:str; magnitude:float|None=Field(default=None,ge=-1,le=5); description:str=Field(default='',max_length=2000); selected_sector:str|None=None; direction:int=Field(default=1,ge=-1,le=1); severity:str='MEDIUM'
class SimulationIn(BaseModel): name:str=Field(default='Classroom Simulation',min_length=1,max_length=160); market_mode:str='SIMULATED'
class EvaluationConfigIn(BaseModel): return_weight:float=Field(ge=0,le=1); sharpe_weight:float=Field(ge=0,le=1); compliance_weight:float=Field(ge=0,le=1); drawdown_weight:float=Field(ge=0,le=1); diversification_weight:float=Field(ge=0,le=1)
class LoginIn(BaseModel): username:str; password:str
class UserIn(BaseModel): username:str=Field(min_length=3,max_length=80); password:str=Field(min_length=8,max_length=200); role:str; portfolio_id:int|None=None
class CustomerPortfolioIn(InvestorIn): team_name:str=Field(min_length=1,max_length=120)
class TemplateCustomerIn(BaseModel): template_id:int; name:str=Field(min_length=1,max_length=120); team_name:str=Field(min_length=1,max_length=120); capital:float=Field(gt=0)
class EvaluationOverrideIn(BaseModel): overridden_score:float=Field(ge=0,le=100); justification:str=Field(min_length=10,max_length=2000)
class RebalanceLeg(BaseModel): asset_id:int; side:str; quantity:float=Field(gt=0)
class RebalanceIn(BaseModel): legs:list[RebalanceLeg]=Field(min_length=2,max_length=50); reason:str=Field(min_length=3,max_length=1000); expected_outcome:str|None=None; main_risk:str|None=None; confidence_level:int|None=Field(default=None,ge=1,le=5); mandate_connection:str|None=None
class AllocationItem(BaseModel): asset_id:int; weight:float=Field(gt=0,le=1)
class AllocationIn(BaseModel): allocations:list[AllocationItem]=Field(min_length=1,max_length=4); reason:str=Field(default='Target allocation selected by portfolio management team',min_length=3,max_length=1000); expected_outcome:str|None=None; main_risk:str|None=None; confidence_level:int|None=Field(default=None,ge=1,le=5); mandate_connection:str|None=None
def rowdict(x): return {c.name:getattr(x,c.name) for c in x.__table__.columns}
def current_simulation(db): return db.scalar(select(Simulation).order_by(Simulation.id.desc()))
def audit(db,action,entity_type,entity_id=None,before=None,after=None,actor='SYSTEM'):
 db.add(AuditLog(actor=actor,action=action,entity_type=entity_type,entity_id=entity_id,before_json=json.dumps(before,default=str) if before is not None else None,after_json=json.dumps(after,default=str) if after is not None else None))
def require_portfolio(db,pid):
 p=db.get(Portfolio,pid)
 if not p: raise HTTPException(404,'Portfolio not found')
 return p
def require_running(db):
 sim=current_simulation(db)
 if not sim or sim.status!='RUNNING': raise HTTPException(409,'Simulation must be running')
 return sim
def authenticated(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(get_db)):
 if not credentials: raise HTTPException(401,'Authentication required',headers={'WWW-Authenticate':'Bearer'})
 session=db.scalar(select(AuthSession).where(AuthSession.token_hash==token_hash(credentials.credentials)))
 if not session or session.expires_at<=datetime.utcnow(): raise HTTPException(401,'Session expired or invalid')
 user=db.get(User,session.user_id)
 if not user or not user.active: raise HTTPException(403,'Account disabled')
 return user
def admin(user:User=Depends(authenticated)):
 if user.role!='ADMIN': raise HTTPException(403,'Administrator access required')
 return user
def can_access_portfolio(db,user,pid):
 if user.role!='ADMIN':
  if user.portfolio_id==pid:return
  allowed=db.scalar(select(UserPortfolioAccess).where(UserPortfolioAccess.user_id==user.id,UserPortfolioAccess.portfolio_id==pid))
  if not allowed: raise HTTPException(403,'Portfolio belongs to another team')
def assetdict(db,a):
 d=rowdict(a);profile=db.scalar(select(AssetProfile).where(AssetProfile.asset_id==a.id));history=db.scalars(select(AssetPriceHistory).where(AssetPriceHistory.asset_id==a.id).order_by(AssetPriceHistory.id.desc()).limit(12)).all()
 change=(a.price-a.previous_price)/a.previous_price if a.previous_price else 0
 d.update({'simulation_price':a.price,'change_pct':change,'status':'Rising' if change>.001 else ('Falling' if change<-.001 else 'Stable'),'profile':rowdict(profile) if profile else None,'price_history':[{'round':h.round_number,'price':h.simulation_price,'change_pct':h.change_pct} for h in reversed(history)]})
 return d
def require_decision_evidence(sim,event,reason,expected_outcome,main_risk,confidence_level,mandate_connection):
 if sim and sim.status=='RUNNING' and event and (not reason.strip() or not expected_outcome or not main_risk or confidence_level is None or not mandate_connection): raise HTTPException(400,'Active-round decisions require justification, expected outcome, main risk, confidence level and investor-mandate connection')
def add_decision_evidence(db,decision_id,event,expected_outcome,main_risk,confidence_level,mandate_connection):
 if expected_outcome and main_risk and confidence_level is not None and mandate_connection:
  round_row=db.scalar(select(SimulationRound).where(SimulationRound.event_id==event.id)) if event else None;db.add(DecisionEvidence(decision_id=decision_id,expected_outcome=expected_outcome,main_risk=main_risk,confidence_level=confidence_level,mandate_connection=mandate_connection,round_number=round_row.round_number if round_row else None))

@app.get('/api/state')
def state(db:Session=Depends(get_db),user:User=Depends(authenticated)):
 sim=current_simulation(db)
 if user.role=='ADMIN': portfolios=db.scalars(select(Portfolio)).all()
 else:
  access_ids=set(db.scalars(select(UserPortfolioAccess.portfolio_id).where(UserPortfolioAccess.user_id==user.id)).all());
  if user.portfolio_id: access_ids.add(user.portfolio_id)
  portfolios=db.scalars(select(Portfolio).where(Portfolio.id.in_(access_ids))).all() if access_ids else []
 investor_ids={p.investor_id for p in portfolios}
 current_round=db.scalar(select(SimulationRound).order_by(SimulationRound.round_number.desc()))
 return {'user':{'username':user.username,'role':user.role,'portfolio_id':user.portfolio_id},'simulation':rowdict(sim) if sim else None,'round':rowdict(current_round) if current_round else None,'investors':[rowdict(x) for x in db.scalars(select(Investor)).all() if user.role=='ADMIN' or x.id in investor_ids],'assets':[assetdict(db,x) for x in db.scalars(select(Asset)).all()],'portfolios':[portfolio_summary(db,x) for x in portfolios],'events':[rowdict(x) for x in db.scalars(select(MarketEvent).order_by(MarketEvent.id.desc())).all()]}

@app.post('/api/auth/login')
def login(x:LoginIn,db:Session=Depends(get_db)):
 user=db.scalar(select(User).where(User.username==x.username))
 if not user or not user.active or not verify_password(x.password,user.password_hash): raise HTTPException(401,'Invalid username or password')
 raw=new_token();db.add(AuthSession(user_id=user.id,token_hash=token_hash(raw),expires_at=token_expiry()));audit(db,'USER_LOGIN','user',user.id,actor=user.username);db.commit()
 return {'access_token':raw,'token_type':'bearer','user':{'id':user.id,'username':user.username,'role':user.role,'portfolio_id':user.portfolio_id}}

@app.post('/api/auth/logout')
def logout(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(get_db),user:User=Depends(authenticated)):
 session=db.scalar(select(AuthSession).where(AuthSession.token_hash==token_hash(credentials.credentials)));db.delete(session);audit(db,'USER_LOGOUT','user',user.id,actor=user.username);db.commit();return {'ok':True}

@app.post('/api/users')
def create_user(x:UserIn,db:Session=Depends(get_db),acting:User=Depends(admin)):
 role=x.role.upper()
 if role not in ('ADMIN','TEAM'): raise HTTPException(400,'Role must be ADMIN or TEAM')
 if role=='TEAM' and not x.portfolio_id: raise HTTPException(400,'Team users require a portfolio')
 if x.portfolio_id and not db.get(Portfolio,x.portfolio_id): raise HTTPException(404,'Portfolio not found')
 if db.scalar(select(User).where(User.username==x.username)): raise HTTPException(409,'Username already exists')
 user=User(username=x.username,password_hash=hash_password(x.password),role=role,portfolio_id=x.portfolio_id);db.add(user);db.flush();audit(db,'USER_CREATED','user',user.id,after={'username':user.username,'role':role,'portfolio_id':x.portfolio_id},actor=acting.username);db.commit();return {'id':user.id,'username':user.username,'role':role,'portfolio_id':user.portfolio_id}
def portfolio_summary(db,p):
 inv=db.get(Investor,p.investor_id); hs=db.scalars(select(Holding).where(Holding.portfolio_id==p.id)).all(); items=[]; invested=0
 for h in hs:
  a=db.get(Asset,h.asset_id);profile=db.scalar(select(AssetProfile).where(AssetProfile.asset_id==a.id));val=h.quantity*a.price;invested+=val;reference=profile.reference_price if profile else a.previous_price;items.append({'asset_id':a.id,'symbol':a.symbol,'kind':a.kind,'sector':profile.sector if profile else a.kind,'quantity':h.quantity,'price':a.price,'previous_price':a.previous_price,'change_pct':(a.price-a.previous_price)/a.previous_price if a.previous_price else 0,'value':val,'unrealized_pl':h.quantity*(a.price-reference)})
 value=invested+p.cash; ret=(value-p.initial_value)/p.initial_value if p.initial_value else 0
 for item in items:item['allocation']=item['value']/value if value else 0;item['contribution']=item['quantity']*(item['price']-item['previous_price'])
 energy=sum(i['allocation'] for i in items if i['sector'] in ('Refinery','Oil & Gas Exploration','Oil Marketing'))
 relationships=[]
 for index,left in enumerate(items):
  for right in items[index+1:]:
   corr=correlation(left['symbol'],right['symbol']);relationships.append({'left':left['symbol'],'right':right['symbol'],'correlation':corr,'level':'High' if corr>=.70 else ('Moderate' if corr>=.45 else 'Low')})
 concentration=sum(i['allocation']**2 for i in items)+(p.cash/value if value else 0)**2;diversification=max(0,min(100,(1-concentration)*140))
 return {'id':p.id,'team_name':p.team_name,'investor':inv.name,'investor_id':inv.id,'cash':p.cash,'initial_value':p.initial_value,'value':value,'profit_loss':value-p.initial_value,'return':ret,'locked':p.locked,'energy_exposure':energy,'diversification_score':diversification,'diversification_warning':'High energy-sector concentration.' if energy>.60 else None,'relationships':relationships,'holdings':items}
@app.post('/api/demo')
def demo(db:Session=Depends(get_db)):
 if db.scalar(select(User)): raise HTTPException(409,'Demo bootstrap is disabled after accounts have been created')
 for t in [AuthSession,User,AuditLog,ComplianceViolation,EvaluationConfig,Simulation,Decision,Holding,Snapshot,Portfolio,MarketEvent,Asset,Investor]: db.query(t).delete()
 sim=Simulation(name='Demo Classroom Simulation',status='RUNNING',market_mode='SIMULATED',started_at=datetime.utcnow());db.add(sim);db.flush()
 db.add(EvaluationConfig(simulation_id=sim.id,locked=True))
 inv=Investor(name='Investor A',capital=1_000_000,risk_profile='Moderate',horizon='1 year',target_return=.12,max_risk=.18,max_equity=.55,min_liquidity=.05); db.add(inv);db.flush()
 assets=[
 Asset(symbol='ENGRO',name='Engro (simulation)',kind='STOCK',price=320,previous_price=320,expected_return=.16,volatility=.24,data_status='SIMULATED'),
 Asset(symbol='HBL',name='HBL (simulation)',kind='STOCK',price=155,previous_price=155,expected_return=.14,volatility=.22,data_status='SIMULATED'),
 Asset(symbol='TBILL-1Y',name='1Y T-Bill',kind='TBILL',price=90090,previous_price=90090,expected_return=.11,volatility=.02,face_value=100000,market_yield=.11,maturity_years=1,data_status='SIMULATED'),
 Asset(symbol='CBILL-90D',name='90D Commercial Bill',kind='COMMERCIAL_BILL',price=97365,previous_price=97365,expected_return=.115,volatility=.035,face_value=100000,market_yield=.11,maturity_years=90/365,data_status='SIMULATED'),
 Asset(symbol='BOND-5Y',name='5Y Coupon Bond',kind='BOND',price=100000,previous_price=100000,expected_return=.12,volatility=.07,face_value=100000,coupon_rate=.12,market_yield=.12,maturity_years=5,data_status='SIMULATED')]
 db.add_all(assets);db.flush()
 for item in PSX_STOCKS:
  a=Asset(symbol=item['symbol'],name=item['name'],kind='STOCK',price=item['price'],previous_price=item['price'],expected_return=.12,volatility=item['volatility'],data_status='SIMULATED');db.add(a);db.flush()
  profile={k:v for k,v in item.items() if k not in ('name','price')};profile['asset_id']=a.id;profile['reference_price']=item['price'];profile['volatility_level']=profile.pop('volatility');profile['dividend_characteristic']=profile.pop('dividend');db.add(AssetProfile(**profile));db.add(AssetPriceHistory(asset_id=a.id,round_number=0,previous_price=a.price,simulation_price=a.price,change_pct=0))
 db.add(SimulationRound(simulation_id=sim.id,round_number=0,label='Market Opening'))
 p=Portfolio(investor_id=inv.id,team_name='Team Alpha',cash=50000,initial_value=1_000_000,locked=True);db.add(p);db.flush()
 allocations=[(assets[0],200000),(assets[1],200000),(assets[2],200000),(assets[3],100000),(assets[4],250000)]
 for a,amt in allocations: db.add(Holding(portfolio_id=p.id,asset_id=a.id,quantity=amt/a.price))
 admin_password=new_token()[:18];team_password=new_token()[:18]
 db.add(Snapshot(portfolio_id=p.id,value=1_000_000,cash=50000,return_pct=0));db.add_all([User(username='admin',password_hash=hash_password(admin_password),role='ADMIN'),User(username='teamalpha',password_hash=hash_password(team_password),role='TEAM',portfolio_id=p.id)]);audit(db,'SIMULATION_STARTED','simulation',sim.id,after=rowdict(sim),actor='ADMIN');db.commit(); return {'ok':True,'simulation_id':sim.id,'demo_accounts':{'admin':{'username':'admin','password':admin_password},'team':{'username':'teamalpha','password':team_password}}}

@app.post('/api/simulations')
def create_simulation(x:SimulationIn,db:Session=Depends(get_db),user:User=Depends(admin)):
 existing=current_simulation(db)
 if existing and existing.status in ('RUNNING','PAUSED'): raise HTTPException(409,'Finish the active simulation first')
 mode=x.market_mode.upper()
 if mode not in ('SIMULATED','REAL','DELAYED'): raise HTTPException(400,'Market mode must be SIMULATED, REAL or DELAYED')
 sim=Simulation(name=x.name,market_mode=mode);db.add(sim);db.flush();db.add(EvaluationConfig(simulation_id=sim.id));audit(db,'SIMULATION_CREATED','simulation',sim.id,after=rowdict(sim),actor='ADMIN');db.commit();db.refresh(sim);return rowdict(sim)

@app.post('/api/simulations/{sid}/start')
def start_simulation(sid:int,db:Session=Depends(get_db),user:User=Depends(admin)):
 sim=db.get(Simulation,sid)
 if not sim: raise HTTPException(404,'Simulation not found')
 if sim.status!='DRAFT': raise HTTPException(409,'Only a draft simulation can be started')
 unlocked=db.scalar(select(Portfolio).where(Portfolio.locked==False))
 if unlocked: raise HTTPException(409,'All portfolios must be locked before the simulation starts')
 cfg=db.scalar(select(EvaluationConfig).where(EvaluationConfig.simulation_id==sid))
 if not cfg: raise HTTPException(409,'Evaluation configuration is missing')
 cfg.locked=True;sim.status='RUNNING';sim.started_at=datetime.utcnow();audit(db,'SIMULATION_STARTED','simulation',sid,actor='ADMIN');db.commit();return rowdict(sim)

@app.post('/api/simulations/{sid}/pause')
def pause_simulation(sid:int,db:Session=Depends(get_db),user:User=Depends(admin)):
 sim=db.get(Simulation,sid)
 if not sim: raise HTTPException(404,'Simulation not found')
 if sim.status!='RUNNING': raise HTTPException(409,'Only a running simulation can be paused')
 sim.status='PAUSED';audit(db,'SIMULATION_PAUSED','simulation',sid,actor='ADMIN');db.commit();return rowdict(sim)

@app.post('/api/simulations/{sid}/resume')
def resume_simulation(sid:int,db:Session=Depends(get_db),user:User=Depends(admin)):
 sim=db.get(Simulation,sid)
 if not sim: raise HTTPException(404,'Simulation not found')
 if sim.status!='PAUSED': raise HTTPException(409,'Only a paused simulation can be resumed')
 sim.status='RUNNING';audit(db,'SIMULATION_RESUMED','simulation',sid,actor='ADMIN');db.commit();return rowdict(sim)

@app.post('/api/simulations/{sid}/end')
def end_simulation(sid:int,db:Session=Depends(get_db),user:User=Depends(admin)):
 sim=db.get(Simulation,sid)
 if not sim: raise HTTPException(404,'Simulation not found')
 if sim.status not in ('RUNNING','PAUSED'): raise HTTPException(409,'Simulation is not active')
 for p in db.scalars(select(Portfolio)).all(): snapshot(db,p,commit=False)
 sim.status='ENDED';sim.ended_at=datetime.utcnow();audit(db,'SIMULATION_ENDED','simulation',sid,actor='ADMIN');db.commit();return rowdict(sim)

@app.put('/api/simulations/{sid}/evaluation-config')
def configure_evaluation(sid:int,x:EvaluationConfigIn,db:Session=Depends(get_db),user:User=Depends(admin)):
 cfg=db.scalar(select(EvaluationConfig).where(EvaluationConfig.simulation_id==sid))
 if not cfg: raise HTTPException(404,'Evaluation configuration not found')
 if cfg.locked: raise HTTPException(409,'Evaluation configuration is locked')
 values=x.model_dump()
 if abs(sum(values.values())-1)>1e-9: raise HTTPException(400,'Evaluation weights must sum to 1.0')
 for key,value in values.items(): setattr(cfg,key,value)
 audit(db,'EVALUATION_CONFIG_UPDATED','evaluation_config',cfg.id,after=values,actor='ADMIN');db.commit();return rowdict(cfg)
@app.post('/api/investors')
def add_investor(x:InvestorIn,db:Session=Depends(get_db),user:User=Depends(admin)):
 if x.risk_profile not in ('Conservative','Moderate','Aggressive'): raise HTTPException(400,'Invalid risk profile')
 o=Investor(**x.model_dump());db.add(o);db.flush();audit(db,'INVESTOR_CREATED','investor',o.id,after=rowdict(o),actor='ADMIN');db.commit();db.refresh(o);return rowdict(o)

@app.post('/api/customers-with-portfolio')
def add_customer_portfolio(x:CustomerPortfolioIn,db:Session=Depends(get_db),user:User=Depends(authenticated)):
 if x.risk_profile not in ('Conservative','Moderate','Aggressive'): raise HTTPException(400,'Invalid risk profile')
 values=x.model_dump(exclude={'team_name'});investor=Investor(**values);db.add(investor);db.flush();portfolio=Portfolio(investor_id=investor.id,team_name=x.team_name,cash=investor.capital,initial_value=investor.capital);db.add(portfolio);db.flush();snapshot(db,portfolio,commit=False)
 if user.role=='TEAM': db.add(UserPortfolioAccess(user_id=user.id,portfolio_id=portfolio.id))
 audit(db,'CUSTOMER_PORTFOLIO_CREATED','portfolio',portfolio.id,after={'investor':rowdict(investor),'portfolio':rowdict(portfolio)},actor=user.username);db.commit();return {'investor':rowdict(investor),'portfolio':rowdict(portfolio)}

@app.post('/api/assets/seed-psx')
def seed_psx_assets(db:Session=Depends(get_db),user:User=Depends(admin)):
 created=[]
 for item in PSX_STOCKS:
  asset=db.scalar(select(Asset).where(Asset.symbol==item['symbol']))
  if not asset:
   asset=Asset(symbol=item['symbol'],name=item['name'],kind='STOCK',price=item['price'],previous_price=item['price'],expected_return=.12,volatility=item['volatility'],data_status='SIMULATED');db.add(asset);db.flush();created.append(item['symbol'])
  profile=db.scalar(select(AssetProfile).where(AssetProfile.asset_id==asset.id))
  if not profile:
   values={k:v for k,v in item.items() if k not in ('name','price')};values['asset_id']=asset.id;values['reference_price']=item['price'];values['volatility_level']=values.pop('volatility');values['dividend_characteristic']=values.pop('dividend');db.add(AssetProfile(**values));db.add(AssetPriceHistory(asset_id=asset.id,round_number=0,previous_price=asset.price,simulation_price=asset.price,change_pct=0))
 audit(db,'PSX_ASSET_MASTER_SEEDED','asset',after={'created':created},actor=user.username);db.commit();return {'ok':True,'created':created,'symbols':[x['symbol'] for x in PSX_STOCKS]}

def seed_activity_catalog(db):
 for item in MANDATES:
  if not db.scalar(select(InvestorMandateTemplate).where(InvestorMandateTemplate.code==item['code'])): db.add(InvestorMandateTemplate(**item))
 db.flush()
 for item in SCENARIOS:
  if db.scalar(select(ScenarioPack).where(ScenarioPack.code==item['code'])): continue
  pack=ScenarioPack(code=item['code'],name=item['name'],description=item['description'],learning_objective=item['learning_objective'],instructor_notes=item['instructor_notes']);db.add(pack);db.flush()
  for sequence,step in enumerate(item['steps'],1):
   name,event_type,magnitude,sector,severity,relationships=step;db.add(ScenarioStep(pack_id=pack.id,sequence=sequence,event_name=name,event_type=event_type,magnitude=magnitude,selected_sector=sector,severity=severity,expected_relationships=relationships,instructor_notes=item['instructor_notes']))

@app.post('/api/activity-catalog/seed')
def seed_catalog(db:Session=Depends(get_db),user:User=Depends(admin)):
 seed_activity_catalog(db);audit(db,'ACTIVITY_CATALOG_SEEDED','activity_catalog',actor=user.username);db.commit();return {'ok':True,'mandates':db.query(InvestorMandateTemplate).count(),'scenario_packs':db.query(ScenarioPack).count()}

@app.get('/api/mandate-templates')
def mandate_templates(db:Session=Depends(get_db),user:User=Depends(authenticated)):
 seed_activity_catalog(db);db.commit();return [rowdict(x) for x in db.scalars(select(InvestorMandateTemplate).order_by(InvestorMandateTemplate.id)).all()]

@app.post('/api/customers-from-template')
def customer_from_template(x:TemplateCustomerIn,db:Session=Depends(get_db),user:User=Depends(authenticated)):
 template=db.get(InvestorMandateTemplate,x.template_id)
 if not template: raise HTTPException(404,'Investor mandate template not found')
 payload=CustomerPortfolioIn(name=x.name,team_name=x.team_name,capital=x.capital,risk_profile=template.risk_profile,horizon=template.horizon,target_return=template.target_return,max_risk=template.max_risk,max_equity=template.max_equity,min_liquidity=template.min_liquidity)
 return add_customer_portfolio(payload,db,user)

@app.get('/api/scenario-packs')
def scenario_packs(db:Session=Depends(get_db),user:User=Depends(admin)):
 seed_activity_catalog(db);db.commit();packs=[]
 for pack in db.scalars(select(ScenarioPack).order_by(ScenarioPack.id)).all():
  steps=[rowdict(x) for x in db.scalars(select(ScenarioStep).where(ScenarioStep.pack_id==pack.id).order_by(ScenarioStep.sequence)).all()];packs.append({**rowdict(pack),'steps':steps})
 return packs

@app.post('/api/scenario-packs/{pack_id}/steps/{sequence}/trigger')
def trigger_scenario_step(pack_id:int,sequence:int,db:Session=Depends(get_db),user:User=Depends(admin)):
 step=db.scalar(select(ScenarioStep).where(ScenarioStep.pack_id==pack_id,ScenarioStep.sequence==sequence))
 if not step: raise HTTPException(404,'Scenario step not found')
 return event(EventIn(name=step.event_name,event_type=step.event_type,magnitude=step.magnitude,description='Instructor scenario event',selected_sector=step.selected_sector,severity=step.severity),db,user)
@app.post('/api/portfolios')
def add_portfolio(x:PortfolioIn,db:Session=Depends(get_db),user:User=Depends(admin)):
 inv=db.get(Investor,x.investor_id); 
 if not inv: raise HTTPException(404,'Investor not found')
 sim=current_simulation(db)
 if sim and sim.status!='DRAFT': raise HTTPException(409,'Portfolios can only be created before simulation start')
 o=Portfolio(investor_id=inv.id,team_name=x.team_name,cash=inv.capital,initial_value=inv.capital);db.add(o);db.flush();audit(db,'PORTFOLIO_CREATED','portfolio',o.id,after=rowdict(o),actor=x.team_name);db.commit();db.refresh(o);return rowdict(o)
@app.post('/api/portfolios/{pid}/lock')
def lock(pid:int,db:Session=Depends(get_db),user:User=Depends(authenticated)):
 p=require_portfolio(db,pid)
 can_access_portfolio(db,user,pid)
 if p.locked: raise HTTPException(409,'Portfolio is already locked')
 p.locked=True;audit(db,'PORTFOLIO_LOCKED','portfolio',pid,actor=p.team_name);snapshot(db,p,commit=False);db.commit();return {'ok':True}
@app.post('/api/portfolios/{pid}/trade')
def trade(pid:int,x:TradeIn,db:Session=Depends(get_db),user:User=Depends(authenticated)):
 p=require_portfolio(db,pid);sim=current_simulation(db)
 can_access_portfolio(db,user,pid)
 if sim and sim.status in ('PAUSED','ENDED'): raise HTTPException(409,'Transactions are disabled while simulation is paused or ended')
 if sim and sim.status=='RUNNING' and not p.locked: raise HTTPException(409,'Portfolio must be locked before trading during the simulation')
 market=x.market_type.upper();act=x.action.upper()
 if market not in ('PRIMARY','SECONDARY'): raise HTTPException(400,'Market type must be PRIMARY or SECONDARY')
 if market=='PRIMARY' and act!='BUY': raise HTTPException(400,'Primary market permits purchases only')
 a=db.get(Asset,x.asset_id) if x.asset_id else None
 latest_event=db.scalar(select(MarketEvent).order_by(MarketEvent.id.desc()))
 require_decision_evidence(sim,latest_event,x.reason,x.expected_outcome,x.main_risk,x.confidence_level,x.mandate_connection)
 if act=='HOLD':
  d=Decision(portfolio_id=pid,asset_id=x.asset_id,action=act,reason=x.reason,price=a.price if a else 0,event_id=latest_event.id if latest_event else None);db.add(d);db.flush();db.add(TradeContext(decision_id=d.id,market_type=market));add_decision_evidence(db,d.id,latest_event,x.expected_outcome,x.main_risk,x.confidence_level,x.mandate_connection);audit(db,'DECISION_RECORDED','decision',d.id,after={**rowdict(d),'market_type':market},actor=p.team_name);db.commit();return {'ok':True,'decision_id':d.id}
 if not a or x.quantity<=0: raise HTTPException(400,'Asset and positive quantity required')
 if act not in ('BUY','SELL'): raise HTTPException(400,'Use BUY, SELL or HOLD')
 cost=x.quantity*a.price; h=db.scalar(select(Holding).where(Holding.portfolio_id==pid,Holding.asset_id==a.id))
 before=portfolio_summary(db,p)
 if act=='BUY':
  if cost>p.cash+1e-6: raise HTTPException(400,'Insufficient cash')
  p.cash-=cost
  if h:h.quantity+=x.quantity
  else:db.add(Holding(portfolio_id=pid,asset_id=a.id,quantity=x.quantity))
 elif act=='SELL':
  if not h or x.quantity>h.quantity+1e-6: raise HTTPException(400,'Insufficient holding')
  h.quantity-=x.quantity;p.cash+=cost
 d=Decision(portfolio_id=pid,asset_id=a.id,action=act,quantity=x.quantity,price=a.price,reason=x.reason,event_id=latest_event.id if latest_event else None);db.add(d);db.flush();db.add(TradeContext(decision_id=d.id,market_type=market));add_decision_evidence(db,d.id,latest_event,x.expected_outcome,x.main_risk,x.confidence_level,x.mandate_connection);after=portfolio_summary(db,p);audit(db,'TRANSACTION_EXECUTED','decision',d.id,before=before,after={**after,'market_type':market},actor=p.team_name);snapshot(db,p,commit=False);db.commit();return {'ok':True,'decision_id':d.id,'market_type':market}

@app.post('/api/portfolios/{pid}/rebalance')
def rebalance(pid:int,x:RebalanceIn,db:Session=Depends(get_db),user:User=Depends(authenticated)):
 p=require_portfolio(db,pid);can_access_portfolio(db,user,pid);sim=require_running(db)
 if not p.locked: raise HTTPException(409,'Portfolio must be locked before rebalancing')
 holdings={h.asset_id:h for h in db.scalars(select(Holding).where(Holding.portfolio_id==pid)).all()}
 proposed={aid:h.quantity for aid,h in holdings.items()};cash=p.cash;resolved=[]
 for leg in x.legs:
  asset=db.get(Asset,leg.asset_id)
  if not asset: raise HTTPException(404,f'Asset {leg.asset_id} not found')
  side=leg.side.upper()
  if side=='SELL':
   if leg.quantity>proposed.get(asset.id,0)+1e-6: raise HTTPException(400,f'Insufficient {asset.symbol} holding')
   proposed[asset.id]=proposed.get(asset.id,0)-leg.quantity;cash+=leg.quantity*asset.price
  elif side=='BUY': cash-=leg.quantity*asset.price;proposed[asset.id]=proposed.get(asset.id,0)+leg.quantity
  else: raise HTTPException(400,'Rebalance side must be BUY or SELL')
  resolved.append((asset,side,leg.quantity))
 if cash < -1e-6: raise HTTPException(400,'Rebalance would create a negative cash balance')
 before=portfolio_summary(db,p);latest_event=db.scalar(select(MarketEvent).order_by(MarketEvent.id.desc()));require_decision_evidence(sim,latest_event,x.reason,x.expected_outcome,x.main_risk,x.confidence_level,x.mandate_connection);decision_ids=[]
 for asset,side,quantity in resolved:
  holding=holdings.get(asset.id)
  if holding: holding.quantity=proposed[asset.id]
  else:
   holding=Holding(portfolio_id=pid,asset_id=asset.id,quantity=proposed[asset.id]);db.add(holding);holdings[asset.id]=holding
  d=Decision(portfolio_id=pid,asset_id=asset.id,action='REBALANCE_'+side,quantity=quantity,price=asset.price,reason=x.reason,event_id=latest_event.id if latest_event else None);db.add(d);db.flush();add_decision_evidence(db,d.id,latest_event,x.expected_outcome,x.main_risk,x.confidence_level,x.mandate_connection);decision_ids.append(d.id)
 p.cash=cash;db.flush();after=portfolio_summary(db,p);audit(db,'PORTFOLIO_REBALANCED','portfolio',pid,before=before,after={'portfolio':after,'decision_ids':decision_ids},actor=p.team_name);snapshot(db,p,commit=False);db.commit();return {'ok':True,'decision_ids':decision_ids,'portfolio':after}

@app.post('/api/portfolios/{pid}/target-allocation')
def target_allocation(pid:int,x:AllocationIn,db:Session=Depends(get_db),user:User=Depends(authenticated)):
 p=require_portfolio(db,pid);can_access_portfolio(db,user,pid);sim=current_simulation(db)
 if sim and sim.status in ('PAUSED','ENDED'): raise HTTPException(409,'Allocation changes are disabled while simulation is paused or ended')
 ids=[item.asset_id for item in x.allocations]
 if len(ids)!=len(set(ids)): raise HTTPException(400,'Each asset can appear only once')
 total_weight=sum(item.weight for item in x.allocations)
 if total_weight>1.000001: raise HTTPException(400,'Total allocation cannot exceed 100%')
 assets={aid:db.get(Asset,aid) for aid in ids}
 if any(asset is None for asset in assets.values()): raise HTTPException(404,'One or more assets were not found')
 before=portfolio_summary(db,p);total_value=before['value'];existing={h.asset_id:h for h in db.scalars(select(Holding).where(Holding.portfolio_id==pid)).all()};targets={item.asset_id:(total_value*item.weight/assets[item.asset_id].price) for item in x.allocations};latest_event=db.scalar(select(MarketEvent).order_by(MarketEvent.id.desc()));require_decision_evidence(sim,latest_event,x.reason,x.expected_outcome,x.main_risk,x.confidence_level,x.mandate_connection);decision_ids=[]
 for asset_id in set(existing)|set(targets):
  holding=existing.get(asset_id);old_qty=holding.quantity if holding else 0;new_qty=targets.get(asset_id,0);delta=new_qty-old_qty
  if holding: holding.quantity=new_qty
  elif new_qty>0: db.add(Holding(portfolio_id=pid,asset_id=asset_id,quantity=new_qty))
  if abs(delta)>1e-8:
   asset=db.get(Asset,asset_id);d=Decision(portfolio_id=pid,asset_id=asset_id,action='REBALANCE_BUY' if delta>0 else 'REBALANCE_SELL',quantity=abs(delta),price=asset.price,reason=x.reason,event_id=latest_event.id if latest_event else None);db.add(d);db.flush();add_decision_evidence(db,d.id,latest_event,x.expected_outcome,x.main_risk,x.confidence_level,x.mandate_connection);decision_ids.append(d.id)
 p.cash=total_value*(1-total_weight);db.flush();after=portfolio_summary(db,p);audit(db,'TARGET_ALLOCATION_SAVED','portfolio',pid,before=before,after={'portfolio':after,'weights':{str(i.asset_id):i.weight for i in x.allocations}},actor=p.team_name);snapshot(db,p,commit=False);db.commit();return {'ok':True,'decision_ids':decision_ids,'portfolio':after}
@app.post('/api/events')
def event(x:EventIn,db:Session=Depends(get_db),user:User=Depends(admin)):
 sim=require_running(db);supported={'STOCK_SHOCK','YIELD_SHOCK','MIXED','RATE_UP','RATE_DOWN','OIL_UP','OIL_DOWN','MARKET_BOOM','MARKET_CRASH','GROWTH','SLOWDOWN','DIVIDEND','SECTOR_SHOCK','CUSTOM'}
 if x.event_type not in supported: raise HTTPException(400,'Unsupported event type')
 portfolios=db.scalars(select(Portfolio)).all();before_values={p.id:portfolio_summary(db,p)['value'] for p in portfolios};mag=x.magnitude if x.magnitude is not None else 0
 e=MarketEvent(name=x.name,event_type=x.event_type,magnitude=mag,description=x.description);db.add(e);db.flush()
 previous_round=db.scalar(select(SimulationRound).order_by(SimulationRound.round_number.desc()));round_number=(previous_round.round_number+1) if previous_round else 1
 db.add(SimulationRound(simulation_id=sim.id,round_number=round_number,event_id=e.id,label=x.name))
 for a in db.scalars(select(Asset)).all():
  a.previous_price=a.price
  profile=db.scalar(select(AssetProfile).where(AssetProfile.asset_id==a.id))
  if a.kind=='STOCK' and profile:
   change=response(profile,x.event_type,round_number,x.magnitude,x.selected_sector,x.direction,x.severity);a.price=max(.01,a.price*(1+change));db.add(AssetPriceHistory(asset_id=a.id,event_id=e.id,round_number=round_number,previous_price=a.previous_price,simulation_price=a.price,change_pct=change))
  elif a.kind=='STOCK': a.price=max(.01,a.price*(1+generic_stock_response(a.symbol,x.event_type,round_number,x.magnitude,x.direction,x.severity)))
  elif x.event_type in ('YIELD_SHOCK','RATE_UP','RATE_DOWN') and a.kind in ('TBILL','COMMERCIAL_BILL','BOND'):
   yield_move=mag if x.event_type=='YIELD_SHOCK' else (.01 if x.event_type=='RATE_UP' else -.01)
   a.market_yield=max(0,a.market_yield+yield_move*.65)
   if a.kind=='TBILL':a.price=tbill_price(a.face_value,a.market_yield,a.maturity_years)
   elif a.kind=='COMMERCIAL_BILL':a.price=discount_bill_price(a.face_value,a.market_yield,a.maturity_years*365)
   else:a.price=bond_price(a.face_value,a.coupon_rate,a.market_yield,a.maturity_years)
 impacts=[]
 for p in portfolios:
  summary=portfolio_summary(db,p);snapshot(db,p,commit=False);impacts.append({'portfolio_id':p.id,'team':p.team_name,'before':before_values[p.id],'after':summary['value'],'change':summary['value']-before_values[p.id]})
 audit(db,'MARKET_EVENT_CREATED','market_event',e.id,after={'event':rowdict(e),'round':round_number,'portfolio_impacts':impacts},actor='ADMIN');db.commit();return {'ok':True,'event_id':e.id,'round_number':round_number,'portfolio_impacts':impacts,'assets':[assetdict(db,a) for a in db.scalars(select(Asset).where(Asset.kind=='STOCK')).all()]}

@app.post('/api/market/reset')
def reset_market(db:Session=Depends(get_db),user:User=Depends(admin)):
 sim=require_running(db);round_number=(db.scalar(select(SimulationRound).order_by(SimulationRound.round_number.desc())).round_number+1)
 for profile in db.scalars(select(AssetProfile)).all():
  asset=db.get(Asset,profile.asset_id);asset.previous_price=asset.price;asset.price=profile.reference_price;change=(asset.price-asset.previous_price)/asset.previous_price if asset.previous_price else 0;db.add(AssetPriceHistory(asset_id=asset.id,round_number=round_number,previous_price=asset.previous_price,simulation_price=asset.price,change_pct=change))
 db.add(SimulationRound(simulation_id=sim.id,round_number=round_number,label='Market Reset'));audit(db,'MARKET_RESET','simulation',sim.id,actor=user.username)
 for p in db.scalars(select(Portfolio)).all(): snapshot(db,p,commit=False)
 db.commit();return {'ok':True,'round_number':round_number}
def snapshot(db,p,commit=True):
 s=portfolio_summary(db,p);db.add(Snapshot(portfolio_id=p.id,value=s['value'],cash=p.cash,return_pct=s['return']));
 if commit:db.commit()
@app.get('/api/evaluation/{pid}')
def evaluation(pid:int,db:Session=Depends(get_db),user:User=Depends(admin)):
 p=require_portfolio(db,pid); inv=db.get(Investor,p.investor_id); s=portfolio_summary(db,p); total=s['value']; weights=[];vols=[];returns=[];symbols=[];equity=0
 for h in s['holdings']:
  a=db.get(Asset,h['asset_id']);w=h['value']/total if total else 0;weights.append(w);vols.append(a.volatility);returns.append(a.expected_return);symbols.append(a.symbol);equity+=w if a.kind=='STOCK' else 0
 corr=[[correlation(left,right) for right in symbols] for left in symbols];cashw=p.cash/total if total else 0;weights2=weights+[cashw];vol=portfolio_volatility(weights,vols,corr); snaps=db.scalars(select(Snapshot).where(Snapshot.portfolio_id==pid).order_by(Snapshot.id)).all(); vals=[x.value for x in snaps] or [p.initial_value,s['value']]
 decision_rows=db.scalars(select(Decision).where(Decision.portfolio_id==pid).order_by(Decision.id)).all();turnover=sum(d.quantity*d.price for d in decision_rows if d.action!='HOLD')/(p.initial_value or 1);evidence_rows=[]
 for d in decision_rows:
  evidence=db.scalar(select(DecisionEvidence).where(DecisionEvidence.decision_id==d.id));evidence_rows.append({'decision_id':d.id,**rowdict(evidence)} if evidence else {'decision_id':d.id})
 completed_evidence=sum(1 for e in evidence_rows if e.get('expected_outcome'));holds=sum(1 for d in decision_rows if d.action=='HOLD')
 ret=s['return']; rf=.10; sh=sharpe(ret,rf,vol); mdd=max_drawdown(vals); bench=.06; issues=compliance(inv,equity,cashw,vol); metrics={'return':ret,'expected_return':expected_return(weights,returns),'volatility':vol,'sharpe':sh,'max_drawdown':mdd,'benchmark_return':bench,'excess_return':ret-bench,'hhi':hhi(weights2),'turnover':turnover,'decision_count':len(decision_rows),'hold_count':holds,'decision_evidence_completion':completed_evidence/len(decision_rows) if decision_rows else 0}
 sim=current_simulation(db);cfg=db.scalar(select(EvaluationConfig).where(EvaluationConfig.simulation_id==sim.id)) if sim else None
 configured={'return':cfg.return_weight,'sharpe':cfg.sharpe_weight,'compliance':cfg.compliance_weight,'drawdown':cfg.drawdown_weight,'diversification':cfg.diversification_weight} if cfg else None
 sc=score(metrics,issues,configured);decisions=[rowdict(x) for x in decision_rows];override=db.scalar(select(EvaluationOverride).where(EvaluationOverride.portfolio_id==pid).order_by(EvaluationOverride.id.desc()))
 return {'portfolio':s,'investor':rowdict(inv),'metrics':metrics,'violations':issues,'evaluation':sc,'instructor_override':rowdict(override) if override else None,'narrative':narrative(p.team_name,inv,metrics,issues),'decisions':decisions,'decision_evidence':evidence_rows,'history':[{'time':x.created_at.isoformat(),'value':x.value,'return':x.return_pct} for x in snaps]}

@app.post('/api/evaluation/{pid}/override')
def override_evaluation(pid:int,x:EvaluationOverrideIn,db:Session=Depends(get_db),user:User=Depends(admin)):
 result=evaluation(pid,db,user);override=EvaluationOverride(portfolio_id=pid,instructor_id=user.id,original_score=result['evaluation']['total'],overridden_score=x.overridden_score,justification=x.justification);db.add(override);db.flush();audit(db,'EVALUATION_OVERRIDDEN','evaluation_override',override.id,after=rowdict(override),actor=user.username);db.commit();return rowdict(override)

@app.get('/api/debrief/{pid}')
def debrief(pid:int,db:Session=Depends(get_db),user:User=Depends(admin)):
 result=evaluation(pid,db,user);events={e.id:e for e in db.scalars(select(MarketEvent)).all()};timeline=[]
 for snap in db.scalars(select(Snapshot).where(Snapshot.portfolio_id==pid).order_by(Snapshot.created_at)).all(): timeline.append({'time':snap.created_at.isoformat(),'type':'PORTFOLIO_VALUE','value':snap.value,'return':snap.return_pct,'benchmark_return':.06})
 for decision in db.scalars(select(Decision).where(Decision.portfolio_id==pid).order_by(Decision.created_at)).all():
  evidence=db.scalar(select(DecisionEvidence).where(DecisionEvidence.decision_id==decision.id));event_row=events.get(decision.event_id);timeline.append({'time':decision.created_at.isoformat(),'type':'TEAM_DECISION','action':decision.action,'asset_id':decision.asset_id,'reason':decision.reason,'event':event_row.name if event_row else None,'evidence':rowdict(evidence) if evidence else None})
 for event_row in events.values(): timeline.append({'time':event_row.created_at.isoformat(),'type':'MARKET_EVENT','name':event_row.name,'event_type':event_row.event_type,'magnitude':event_row.magnitude})
 for price_row in db.scalars(select(AssetPriceHistory).where(AssetPriceHistory.event_id.is_not(None)).order_by(AssetPriceHistory.created_at)).all():
  asset=db.get(Asset,price_row.asset_id);timeline.append({'time':price_row.created_at.isoformat(),'type':'ASSET_PRICE_MOVEMENT','asset_id':price_row.asset_id,'symbol':asset.symbol if asset else None,'round_number':price_row.round_number,'previous_price':price_row.previous_price,'price':price_row.simulation_price,'change_pct':price_row.change_pct})
 for issue in result['violations']:
  timeline.append({'time':datetime.utcnow().isoformat(),'type':'MANDATE_VIOLATION','name':issue['type'],'severity':issue['severity'],'detail':issue['detail']})
 timeline.append({'time':datetime.utcnow().isoformat(),'type':'RISK_SUMMARY','volatility':result['metrics']['volatility'],'max_drawdown':result['metrics']['max_drawdown'],'benchmark_return':result['metrics']['benchmark_return']})
 timeline.sort(key=lambda x:x['time']);return {'portfolio':result['portfolio'],'investor':result['investor'],'metrics':result['metrics'],'violations':result['violations'],'timeline':timeline}

@app.get('/api/audit-logs')
def audit_logs(limit:int=100,db:Session=Depends(get_db),user:User=Depends(admin)):
 limit=max(1,min(limit,500));return [rowdict(x) for x in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).all()]
@app.get('/api/ml-features')
def ml_features(db:Session=Depends(get_db),user:User=Depends(admin)):
 out=[]
 for p in db.scalars(select(Portfolio)).all():
  e=evaluation(p.id,db);m=e['metrics'];out.append({'portfolio_id':p.id,'team':p.team_name,**m,'violations':len(e['violations']),'decision_count':len(e['decisions'])})
 return out

@app.get('/api/comparison')
def comparison(db:Session=Depends(get_db),user:User=Depends(admin)):
 rows=[]
 for p in db.scalars(select(Portfolio)).all():
  result=evaluation(p.id,db,user);m=result['metrics']
  rows.append({'portfolio_id':p.id,'team':p.team_name,'investor':result['investor']['name'],'value':result['portfolio']['value'],'return':m['return'],'volatility':m['volatility'],'sharpe':m['sharpe'],'max_drawdown':m['max_drawdown'],'excess_return':m['excess_return'],'violations':len(result['violations']),'score':result['evaluation']['total']})
 return sorted(rows,key=lambda x:x['score'],reverse=True)

@app.get('/api/reports/{pid}')
def final_report(pid:int,db:Session=Depends(get_db),user:User=Depends(admin)):
 sim=current_simulation(db)
 if not sim or sim.status!='ENDED': raise HTTPException(409,'Final reports are available only after simulation end')
 result=evaluation(pid,db,user);events=[rowdict(e) for e in db.scalars(select(MarketEvent).order_by(MarketEvent.id)).all()]
 initial=db.scalar(select(Snapshot).where(Snapshot.portfolio_id==pid).order_by(Snapshot.id));final=db.scalar(select(Snapshot).where(Snapshot.portfolio_id==pid).order_by(Snapshot.id.desc()))
 return {'report_type':'FINAL_TEAM_REPORT','generated_at':datetime.utcnow().isoformat(),'simulation':rowdict(sim),'investor':result['investor'],'initial_portfolio':{'value':initial.value if initial else result['portfolio']['initial_value'],'timestamp':initial.created_at.isoformat() if initial else None},'market_journey':{'events':events,'decisions':result['decisions'],'value_history':result['history']},'final_portfolio':result['portfolio'],'calculated_facts':result['metrics'],'rule_based_findings':result['violations'],'evaluation':result['evaluation'],'ai_interpretation':{'provider':'DETERMINISTIC_FALLBACK','text':result['narrative'],'disclaimer':'Interpretation only; all numeric facts come from deterministic calculations.'}}
