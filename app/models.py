from sqlalchemy import String,Float,Integer,Boolean,DateTime,ForeignKey,Text
from sqlalchemy.orm import Mapped,mapped_column
from datetime import datetime
from .db import Base
class Investor(Base):
 __tablename__='investors'; id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String); capital:Mapped[float]=mapped_column(Float); risk_profile:Mapped[str]=mapped_column(String); horizon:Mapped[str]=mapped_column(String,default='1 year'); target_return:Mapped[float]=mapped_column(Float,default=0.10); max_risk:Mapped[float]=mapped_column(Float,default=0.20); max_equity:Mapped[float]=mapped_column(Float,default=0.60); min_liquidity:Mapped[float]=mapped_column(Float,default=0.05)
class Asset(Base):
 __tablename__='assets'; id:Mapped[int]=mapped_column(primary_key=True); symbol:Mapped[str]=mapped_column(String,unique=True); name:Mapped[str]=mapped_column(String); kind:Mapped[str]=mapped_column(String); price:Mapped[float]=mapped_column(Float); previous_price:Mapped[float]=mapped_column(Float); expected_return:Mapped[float]=mapped_column(Float,default=0.10); volatility:Mapped[float]=mapped_column(Float,default=0.15); face_value:Mapped[float]=mapped_column(Float,default=0); coupon_rate:Mapped[float]=mapped_column(Float,default=0); market_yield:Mapped[float]=mapped_column(Float,default=0); maturity_years:Mapped[float]=mapped_column(Float,default=1); data_status:Mapped[str]=mapped_column(String,default='SIMULATED')
class Portfolio(Base):
 __tablename__='portfolios'; id:Mapped[int]=mapped_column(primary_key=True); investor_id:Mapped[int]=mapped_column(ForeignKey('investors.id')); team_name:Mapped[str]=mapped_column(String); cash:Mapped[float]=mapped_column(Float); initial_value:Mapped[float]=mapped_column(Float); locked:Mapped[bool]=mapped_column(Boolean,default=False); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Holding(Base):
 __tablename__='holdings'; id:Mapped[int]=mapped_column(primary_key=True); portfolio_id:Mapped[int]=mapped_column(ForeignKey('portfolios.id')); asset_id:Mapped[int]=mapped_column(ForeignKey('assets.id')); quantity:Mapped[float]=mapped_column(Float)
class Decision(Base):
 __tablename__='decisions'; id:Mapped[int]=mapped_column(primary_key=True); portfolio_id:Mapped[int]=mapped_column(ForeignKey('portfolios.id')); asset_id:Mapped[int|None]=mapped_column(ForeignKey('assets.id'),nullable=True); action:Mapped[str]=mapped_column(String); quantity:Mapped[float]=mapped_column(Float,default=0); price:Mapped[float]=mapped_column(Float,default=0); reason:Mapped[str]=mapped_column(Text,default=''); event_id:Mapped[int|None]=mapped_column(nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class MarketEvent(Base):
 __tablename__='market_events'; id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String); event_type:Mapped[str]=mapped_column(String); magnitude:Mapped[float]=mapped_column(Float); description:Mapped[str]=mapped_column(Text,default=''); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class Snapshot(Base):
 __tablename__='snapshots'; id:Mapped[int]=mapped_column(primary_key=True); portfolio_id:Mapped[int]=mapped_column(ForeignKey('portfolios.id')); value:Mapped[float]=mapped_column(Float); cash:Mapped[float]=mapped_column(Float); return_pct:Mapped[float]=mapped_column(Float); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class Simulation(Base):
 __tablename__='simulations'; id:Mapped[int]=mapped_column(primary_key=True); name:Mapped[str]=mapped_column(String,default='Classroom Simulation'); status:Mapped[str]=mapped_column(String,default='DRAFT'); market_mode:Mapped[str]=mapped_column(String,default='SIMULATED'); started_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True); ended_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class EvaluationConfig(Base):
 __tablename__='evaluation_configs'; id:Mapped[int]=mapped_column(primary_key=True); simulation_id:Mapped[int]=mapped_column(ForeignKey('simulations.id'),unique=True); return_weight:Mapped[float]=mapped_column(Float,default=.30); sharpe_weight:Mapped[float]=mapped_column(Float,default=.20); compliance_weight:Mapped[float]=mapped_column(Float,default=.25); drawdown_weight:Mapped[float]=mapped_column(Float,default=.15); diversification_weight:Mapped[float]=mapped_column(Float,default=.10); locked:Mapped[bool]=mapped_column(Boolean,default=False); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class ComplianceViolation(Base):
 __tablename__='compliance_violations'; id:Mapped[int]=mapped_column(primary_key=True); portfolio_id:Mapped[int]=mapped_column(ForeignKey('portfolios.id')); violation_type:Mapped[str]=mapped_column(String); severity:Mapped[str]=mapped_column(String); detail:Mapped[str]=mapped_column(Text); corrected:Mapped[bool]=mapped_column(Boolean,default=False); detected_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow); corrected_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)

class AuditLog(Base):
 __tablename__='audit_logs'; id:Mapped[int]=mapped_column(primary_key=True); actor:Mapped[str]=mapped_column(String,default='SYSTEM'); action:Mapped[str]=mapped_column(String); entity_type:Mapped[str]=mapped_column(String); entity_id:Mapped[int|None]=mapped_column(Integer,nullable=True); before_json:Mapped[str|None]=mapped_column(Text,nullable=True); after_json:Mapped[str|None]=mapped_column(Text,nullable=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class User(Base):
 __tablename__='users'; id:Mapped[int]=mapped_column(primary_key=True); username:Mapped[str]=mapped_column(String,unique=True,index=True); password_hash:Mapped[str]=mapped_column(String); role:Mapped[str]=mapped_column(String); portfolio_id:Mapped[int|None]=mapped_column(ForeignKey('portfolios.id'),nullable=True); active:Mapped[bool]=mapped_column(Boolean,default=True); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class AuthSession(Base):
 __tablename__='auth_sessions'; id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey('users.id')); token_hash:Mapped[str]=mapped_column(String,unique=True,index=True); expires_at:Mapped[datetime]=mapped_column(DateTime); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class AssetProfile(Base):
 __tablename__='asset_profiles'; id:Mapped[int]=mapped_column(primary_key=True); asset_id:Mapped[int]=mapped_column(ForeignKey('assets.id'),unique=True); symbol:Mapped[str]=mapped_column(String,index=True); sector:Mapped[str]=mapped_column(String); reference_price:Mapped[float]=mapped_column(Float); volatility_level:Mapped[float]=mapped_column(Float); risk_level:Mapped[str]=mapped_column(String); dividend_characteristic:Mapped[str]=mapped_column(String); rate_sensitivity:Mapped[float]=mapped_column(Float); oil_sensitivity:Mapped[float]=mapped_column(Float); growth_sensitivity:Mapped[float]=mapped_column(Float); sentiment_sensitivity:Mapped[float]=mapped_column(Float); sector_sensitivity:Mapped[float]=mapped_column(Float); beta:Mapped[float]=mapped_column(Float)

class SimulationRound(Base):
 __tablename__='simulation_rounds'; id:Mapped[int]=mapped_column(primary_key=True); simulation_id:Mapped[int]=mapped_column(ForeignKey('simulations.id')); round_number:Mapped[int]=mapped_column(Integer); event_id:Mapped[int|None]=mapped_column(ForeignKey('market_events.id'),nullable=True); label:Mapped[str]=mapped_column(String); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class AssetPriceHistory(Base):
 __tablename__='asset_price_history'; id:Mapped[int]=mapped_column(primary_key=True); asset_id:Mapped[int]=mapped_column(ForeignKey('assets.id')); event_id:Mapped[int|None]=mapped_column(ForeignKey('market_events.id'),nullable=True); round_number:Mapped[int]=mapped_column(Integer); previous_price:Mapped[float]=mapped_column(Float); simulation_price:Mapped[float]=mapped_column(Float); change_pct:Mapped[float]=mapped_column(Float); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class TradeContext(Base):
 __tablename__='trade_contexts'; id:Mapped[int]=mapped_column(primary_key=True); decision_id:Mapped[int]=mapped_column(ForeignKey('decisions.id'),unique=True); market_type:Mapped[str]=mapped_column(String); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class UserPortfolioAccess(Base):
 __tablename__='user_portfolio_access'; id:Mapped[int]=mapped_column(primary_key=True); user_id:Mapped[int]=mapped_column(ForeignKey('users.id')); portfolio_id:Mapped[int]=mapped_column(ForeignKey('portfolios.id')); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class InvestorMandateTemplate(Base):
 __tablename__='investor_mandate_templates'; id:Mapped[int]=mapped_column(primary_key=True); code:Mapped[str]=mapped_column(String,unique=True); name:Mapped[str]=mapped_column(String); description:Mapped[str]=mapped_column(Text); risk_profile:Mapped[str]=mapped_column(String); horizon:Mapped[str]=mapped_column(String); target_return:Mapped[float]=mapped_column(Float); max_risk:Mapped[float]=mapped_column(Float); max_equity:Mapped[float]=mapped_column(Float); min_liquidity:Mapped[float]=mapped_column(Float); restrictions:Mapped[str]=mapped_column(Text,default='')

class ScenarioPack(Base):
 __tablename__='scenario_packs'; id:Mapped[int]=mapped_column(primary_key=True); code:Mapped[str]=mapped_column(String,unique=True); name:Mapped[str]=mapped_column(String); description:Mapped[str]=mapped_column(Text); learning_objective:Mapped[str]=mapped_column(Text); instructor_notes:Mapped[str]=mapped_column(Text); active:Mapped[bool]=mapped_column(Boolean,default=True)

class ScenarioStep(Base):
 __tablename__='scenario_steps'; id:Mapped[int]=mapped_column(primary_key=True); pack_id:Mapped[int]=mapped_column(ForeignKey('scenario_packs.id')); sequence:Mapped[int]=mapped_column(Integer); event_name:Mapped[str]=mapped_column(String); event_type:Mapped[str]=mapped_column(String); magnitude:Mapped[float|None]=mapped_column(Float,nullable=True); selected_sector:Mapped[str|None]=mapped_column(String,nullable=True); severity:Mapped[str]=mapped_column(String,default='MEDIUM'); expected_relationships:Mapped[str]=mapped_column(Text); instructor_notes:Mapped[str]=mapped_column(Text)

class DecisionEvidence(Base):
 __tablename__='decision_evidence'; id:Mapped[int]=mapped_column(primary_key=True); decision_id:Mapped[int]=mapped_column(ForeignKey('decisions.id'),unique=True); expected_outcome:Mapped[str]=mapped_column(Text); main_risk:Mapped[str]=mapped_column(Text); confidence_level:Mapped[int]=mapped_column(Integer); mandate_connection:Mapped[str]=mapped_column(Text); round_number:Mapped[int|None]=mapped_column(Integer,nullable=True)

class EvaluationOverride(Base):
 __tablename__='evaluation_overrides'; id:Mapped[int]=mapped_column(primary_key=True); portfolio_id:Mapped[int]=mapped_column(ForeignKey('portfolios.id')); instructor_id:Mapped[int]=mapped_column(ForeignKey('users.id')); original_score:Mapped[float]=mapped_column(Float); overridden_score:Mapped[float]=mapped_column(Float); justification:Mapped[str]=mapped_column(Text); created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
