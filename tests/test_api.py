import os
os.environ['PORTFOLIO_DB_URL']='sqlite://'

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base,get_db
from app.main import app


engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
TestingSession=sessionmaker(bind=engine,autoflush=False,autocommit=False)
Base.metadata.create_all(engine)


def override_db():
 db=TestingSession()
 try:
  yield db
 finally:
  db.close()


app.dependency_overrides[get_db]=override_db
client=TestClient(app)
bootstrap=client.post('/api/demo').json()
login=client.post('/api/auth/login',json=bootstrap['demo_accounts']['admin']).json()
HEADERS={'Authorization':f"Bearer {login['access_token']}"}


def test_demo_creates_running_simulation_and_audit_log():
 assert client.post('/api/demo').status_code==409
 state=client.get('/api/state',headers=HEADERS).json()
 assert state['simulation']['status']=='RUNNING'
 assert state['simulation']['market_mode']=='SIMULATED'
 assert state['portfolios'][0]['locked'] is True
 assert client.get('/api/audit-logs',headers=HEADERS).json()[0]['action']=='USER_LOGIN'


def test_atomic_rebalance_and_team_isolation():
 team=client.post('/api/auth/login',json=bootstrap['demo_accounts']['team']).json()
 headers={'Authorization':f"Bearer {team['access_token']}"}
 state=client.get('/api/state',headers=headers).json();pid=state['portfolios'][0]['id'];stock=state['assets'][0];bill=state['assets'][2]
 before=state['portfolios'][0]['cash']
 payload={'reason':'Reduce equity risk after review','legs':[{'asset_id':stock['id'],'side':'SELL','quantity':10},{'asset_id':bill['id'],'side':'BUY','quantity':.02}]}
 result=client.post(f'/api/portfolios/{pid}/rebalance',json=payload,headers=headers)
 assert result.status_code==200 and len(result.json()['decision_ids'])==2
 bad={'reason':'Invalid oversized rebalance','legs':[{'asset_id':stock['id'],'side':'SELL','quantity':999999},{'asset_id':bill['id'],'side':'BUY','quantity':1}]}
 assert client.post(f'/api/portfolios/{pid}/rebalance',json=bad,headers=headers).status_code==400
 assert client.get('/api/state',headers=headers).json()['portfolios'][0]['cash']!=before


def test_psx_oil_event_has_differentiated_reactions_and_reset():
 state_before=client.get('/api/state',headers=HEADERS).json();portfolio_before=state_before['portfolios'][0]['value'];before={a['symbol']:a['price'] for a in state_before['assets'] if a.get('profile')}
 result=client.post('/api/events',headers=HEADERS,json={'name':'Oil Price +10%','event_type':'OIL_UP','description':'Classroom oil shock'})
 assert result.status_code==200
 after={a['symbol']:a for a in client.get('/api/state',headers=HEADERS).json()['assets'] if a.get('profile')}
 changes={s:round((after[s]['price']/p)-1,6) for s,p in before.items()}
 assert len(set(changes.values()))>4
 assert changes['NRL']>changes['APL']>changes['UBL']
 assert abs(client.get('/api/state',headers=HEADERS).json()['portfolios'][0]['value']-portfolio_before)>.01
 assert client.post('/api/market/reset',headers=HEADERS).status_code==200
 reset={a['symbol']:a for a in client.get('/api/state',headers=HEADERS).json()['assets'] if a.get('profile')}
 assert all(abs(a['price']-a['profile']['reference_price'])<1e-6 for a in reset.values())


def test_target_weights_limit_and_interconnected_portfolio_metrics():
 team=client.post('/api/auth/login',json=bootstrap['demo_accounts']['team']).json();headers={'Authorization':f"Bearer {team['access_token']}"}
 state=client.get('/api/state',headers=headers).json();pid=state['portfolios'][0]['id'];by_symbol={a['symbol']:a for a in state['assets']}
 allocations=[{'asset_id':by_symbol[s]['id'],'weight':.24} for s in ('NRL','ATRL','POL','APL')]
 result=client.post(f'/api/portfolios/{pid}/target-allocation',headers=headers,json={'allocations':allocations,'reason':'Energy allocation classroom test','expected_outcome':'Maintain controlled energy exposure','main_risk':'Oil-price reversal','confidence_level':3,'mandate_connection':'Balances growth with the investor risk ceiling'})
 assert result.status_code==200
 portfolio=result.json()['portfolio']
 assert len(portfolio['holdings'])>=4 and portfolio['energy_exposure']>.90
 assert portfolio['diversification_warning']=='High energy-sector concentration.'
 assert any(r['left']=='NRL' and r['right']=='ATRL' and r['level']=='High' for r in portfolio['relationships'])
 too_many=allocations+[{'asset_id':by_symbol['UBL']['id'],'weight':.01}]
 assert client.post(f'/api/portfolios/{pid}/target-allocation',headers=headers,json={'allocations':too_many,'reason':'Too many assets'}).status_code==422
 primary_sell=client.post(f'/api/portfolios/{pid}/trade',headers=headers,json={'asset_id':by_symbol['NRL']['id'],'action':'SELL','quantity':.01,'reason':'Not allowed in primary','market_type':'PRIMARY'})
 assert primary_sell.status_code==400
 secondary_sell=client.post(f'/api/portfolios/{pid}/trade',headers=headers,json={'asset_id':by_symbol['NRL']['id'],'action':'SELL','quantity':.01,'reason':'Valid secondary sale','market_type':'SECONDARY','expected_outcome':'Maintain controlled energy exposure','main_risk':'Oil-price reversal','confidence_level':3,'mandate_connection':'Balances growth with the investor risk ceiling'})
 assert secondary_sell.status_code==200


def test_admin_customer_save_creates_separate_portfolio_record():
 before=len(client.get('/api/state',headers=HEADERS).json()['portfolios'])
 payload={'name':'Investor B','team_name':'Team Beta','capital':750000,'risk_profile':'Conservative'}
 result=client.post('/api/customers-with-portfolio',headers=HEADERS,json=payload)
 assert result.status_code==200 and result.json()['portfolio']['investor_id']==result.json()['investor']['id']
 assert len(client.get('/api/state',headers=HEADERS).json()['portfolios'])==before+1


def test_portfolio_manager_can_create_and_reopen_own_investor_portfolio():
 team=client.post('/api/auth/login',json=bootstrap['demo_accounts']['team']).json();headers={'Authorization':f"Bearer {team['access_token']}"}
 before=len(client.get('/api/state',headers=headers).json()['portfolios'])
 payload={'name':'PM Customer','team_name':'Team Alpha','capital':500000,'risk_profile':'Moderate'}
 result=client.post('/api/customers-with-portfolio',headers=headers,json=payload)
 assert result.status_code==200
 portfolio_id=result.json()['portfolio']['id'];state=client.get('/api/state',headers=headers).json()
 assert len(state['portfolios'])==before+1 and any(p['id']==portfolio_id for p in state['portfolios'])
 other_admin_portfolio=client.post('/api/customers-with-portfolio',headers=HEADERS,json={'name':'Private Admin Customer','team_name':'Admin Desk','capital':400000,'risk_profile':'Conservative'}).json()['portfolio']['id']
 assert client.post(f'/api/portfolios/{other_admin_portfolio}/trade',headers=headers,json={'action':'HOLD','reason':'Should be denied','market_type':'SECONDARY'}).status_code==403


def test_activity_catalog_is_role_safe_and_pm_can_use_mandate_template():
 team=client.post('/api/auth/login',json=bootstrap['demo_accounts']['team']).json();headers={'Authorization':f"Bearer {team['access_token']}"}
 mandates=client.get('/api/mandate-templates',headers=headers)
 assert mandates.status_code==200 and len(mandates.json())==6
 assert all({'target_return','max_risk','max_equity','min_liquidity','restrictions','horizon'}<=m.keys() for m in mandates.json())
 assert client.get('/api/scenario-packs',headers=headers).status_code==403
 packs=client.get('/api/scenario-packs',headers=HEADERS)
 assert packs.status_code==200 and len(packs.json())==6
 created=client.post('/api/customers-from-template',headers=headers,json={'template_id':mandates.json()[0]['id'],'name':'Template Customer','team_name':'Team Alpha','capital':600000})
 assert created.status_code==200 and created.json()['investor']['target_return']==mandates.json()[0]['target_return']


def test_active_round_requires_and_persists_decision_quality_fields():
 team=client.post('/api/auth/login',json=bootstrap['demo_accounts']['team']).json();headers={'Authorization':f"Bearer {team['access_token']}"}
 pid=client.get('/api/state',headers=headers).json()['portfolios'][0]['id']
 incomplete=client.post(f'/api/portfolios/{pid}/trade',headers=headers,json={'action':'HOLD','reason':'Observe conditions','market_type':'SECONDARY'})
 assert incomplete.status_code==400
 complete=client.post(f'/api/portfolios/{pid}/trade',headers=headers,json={'action':'HOLD','reason':'Avoid unnecessary turnover','market_type':'SECONDARY','expected_outcome':'Preserve value','main_risk':'Missing a rebound','confidence_level':4,'mandate_connection':'Matches the investor risk ceiling'})
 assert complete.status_code==200
 evaluation=client.get(f'/api/evaluation/{pid}',headers=HEADERS).json()
 evidence=next(x for x in evaluation['decision_evidence'] if x['decision_id']==complete.json()['decision_id'])
 assert evidence['expected_outcome']=='Preserve value' and evidence['confidence_level']==4


def test_running_simulation_accepts_event_then_can_end():
 event={'name':'Equity correction','event_type':'STOCK_SHOCK','magnitude':-.05,'description':'Classroom scenario'}
 before={p['id']:p['value'] for p in client.get('/api/state',headers=HEADERS).json()['portfolios']}
 assert client.post('/api/events',json=event,headers=HEADERS).status_code==200
 state=client.get('/api/state',headers=HEADERS).json()
 assert any(abs(p['value']-before[p['id']])>.01 for p in state['portfolios'])
 sid=state['simulation']['id']
 assert client.post(f'/api/simulations/{sid}/end',headers=HEADERS).status_code==200
 assert client.post('/api/events',json=event,headers=HEADERS).status_code==409
 assert client.post(f'/api/portfolios/{state["portfolios"][0]["id"]}/trade',json={'action':'HOLD','reason':'No change'},headers=HEADERS).status_code==409


def test_evaluation_exposes_deterministic_metrics():
 pid=client.get('/api/state',headers=HEADERS).json()['portfolios'][0]['id']
 result=client.get(f'/api/evaluation/{pid}',headers=HEADERS)
 assert result.status_code==200
 metrics=result.json()['metrics']
 assert {'return','expected_return','volatility','sharpe','max_drawdown','excess_return','hhi'}<=metrics.keys()
 assert {'turnover','hold_count','decision_evidence_completion'}<=metrics.keys()


def test_debrief_and_written_instructor_override_are_admin_only():
 pid=client.get('/api/state',headers=HEADERS).json()['portfolios'][0]['id']
 timeline=client.get(f'/api/debrief/{pid}',headers=HEADERS)
 assert timeline.status_code==200
 types={item['type'] for item in timeline.json()['timeline']}
 assert {'MARKET_EVENT','ASSET_PRICE_MOVEMENT','PORTFOLIO_VALUE','TEAM_DECISION','RISK_SUMMARY'}<=types
 assert client.post(f'/api/evaluation/{pid}/override',headers=HEADERS,json={'overridden_score':88,'justification':'Strong mandate-aware reasoning despite short-horizon loss.'}).status_code==200
 team=client.post('/api/auth/login',json=bootstrap['demo_accounts']['team']).json();headers={'Authorization':f"Bearer {team['access_token']}"}
 assert client.get(f'/api/debrief/{pid}',headers=headers).status_code==403


def test_final_report_separates_fact_rule_and_interpretation():
 pid=client.get('/api/state',headers=HEADERS).json()['portfolios'][0]['id']
 report=client.get(f'/api/reports/{pid}',headers=HEADERS)
 assert report.status_code==200
 body=report.json()
 assert body['report_type']=='FINAL_TEAM_REPORT'
 assert {'calculated_facts','rule_based_findings','ai_interpretation'}<=body.keys()
 assert client.get('/api/comparison',headers=HEADERS).status_code==200


def test_team_cannot_access_hidden_evaluation():
 team=client.post('/api/auth/login',json=bootstrap['demo_accounts']['team']).json()
 headers={'Authorization':f"Bearer {team['access_token']}"}
 pid=team['user']['portfolio_id']
 assert client.get(f'/api/evaluation/{pid}',headers=headers).status_code==403
 assert client.get('/api/audit-logs',headers=headers).status_code==403
