def compliance(investor,equity_weight,cash_weight,vol):
 issues=[]
 if equity_weight>investor.max_equity: issues.append({'type':'Equity allocation','severity':'High','detail':f'{equity_weight:.1%} > limit {investor.max_equity:.1%}'})
 if cash_weight<investor.min_liquidity: issues.append({'type':'Liquidity','severity':'Medium','detail':f'{cash_weight:.1%} < minimum {investor.min_liquidity:.1%}'})
 if vol>investor.max_risk: issues.append({'type':'Portfolio risk','severity':'High','detail':f'{vol:.1%} > limit {investor.max_risk:.1%}'})
 return issues
def score(metrics,violations,weights=None):
 w=weights or {'return':.30,'sharpe':.20,'compliance':.25,'drawdown':.15,'diversification':.10}
 ret=max(0,min(100,50+metrics['return']*250)); sh=max(0,min(100,50+metrics['sharpe']*25)); comp=max(0,100-len(violations)*25); dd=max(0,100-metrics['max_drawdown']*300); div=max(0,min(100,(1-metrics['hhi'])*130))
 total=w['return']*ret+w['sharpe']*sh+w['compliance']*comp+w['drawdown']*dd+w['diversification']*div
 return {'total':round(total,1),'components':{'return':round(ret,1),'sharpe':round(sh,1),'compliance':round(comp,1),'drawdown':round(dd,1),'diversification':round(div,1)},'weights':w}
def narrative(team,investor,m,violations):
 direction='positive' if m['return']>=0 else 'negative'; excess=m['return']-m['benchmark_return']
 s=f"{team} produced a {direction} portfolio return of {m['return']:.2%}. Risk-adjusted performance measured by Sharpe ratio was {m['sharpe']:.2f}, with maximum drawdown of {m['max_drawdown']:.2%}. "
 s+=f"The portfolio {'outperformed' if excess>=0 else 'underperformed'} the configured benchmark by {abs(excess):.2%}. "
 s+=('No investor-mandate violations were detected.' if not violations else f"{len(violations)} mandate/compliance issue(s) were detected and should be reviewed against the {investor.risk_profile} investor profile.")
 return s
