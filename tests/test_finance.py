from app.services.finance import *
def test_tbill(): assert round(tbill_price(100000,.12,1),2)==89285.71
def test_discount(): assert discount_bill_price(100000,.12,90)<100000
def test_bond_par(): assert abs(bond_price(1000,.10,.10,5)-1000)<1e-6
def test_portfolio_vol(): assert portfolio_volatility([.5,.5],[.1,.2])>0
def test_sharpe(): assert abs(sharpe(.15,.10,.08)-.625)<1e-12
def test_mdd(): assert abs(max_drawdown([100,120,90,110])-.25)<1e-9
def test_hhi(): assert abs(hhi([.5,.5])-.5)<1e-9
def test_expected_return(): assert abs(expected_return([.4,.6],[.1,.2])-.16)<1e-12
def test_duration_positive_and_modified_lower():
 mac=macaulay_duration(1000,.10,.12,5)
 mod=modified_duration(1000,.10,.12,5)
 assert mac>0 and 0<mod<mac
def test_covariance_reduces_diversified_risk():
 independent=portfolio_volatility([.5,.5],[.2,.2])
 correlated=portfolio_volatility([.5,.5],[.2,.2],[[1,1],[1,1]])
 assert independent<correlated
