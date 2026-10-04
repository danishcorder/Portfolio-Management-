import math, numpy as np
def tbill_price(face,y,t): return face/((1+y)**t)
def discount_bill_price(face,y,days,basis=365): return face/(1+y*(days/basis))
def bond_price(face,coupon_rate,y,n,freq=1):
 c=face*coupon_rate/freq; periods=max(1,int(round(n*freq))); yp=y/freq
 return sum(c/((1+yp)**t) for t in range(1,periods+1))+face/((1+yp)**periods)
def macaulay_duration(face,coupon_rate,y,n,freq=1):
 c=face*coupon_rate/freq; periods=max(1,int(round(n*freq))); yp=y/freq
 flows=[c]*periods; flows[-1]+=face; pv=[cf/((1+yp)**t) for t,cf in enumerate(flows,1)]; p=sum(pv)
 return (sum((t/freq)*v for t,v in enumerate(pv,1))/p) if p else 0
def modified_duration(face,coupon_rate,y,n,freq=1): return macaulay_duration(face,coupon_rate,y,n,freq)/(1+y/freq)
def expected_return(weights,returns): return float(np.dot(weights,returns)) if weights else 0
def portfolio_volatility(weights,vols,corr=None):
 if not weights:return 0
 w=np.array(weights,float); v=np.array(vols,float); corr=np.eye(len(w)) if corr is None else np.array(corr,float); cov=np.outer(v,v)*corr
 return float(math.sqrt(max(0,w@cov@w)))
def sharpe(ret,rf,vol): return (ret-rf)/vol if vol>0 else 0
def max_drawdown(values):
 if not values:return 0
 peak=values[0]; m=0
 for x in values: peak=max(peak,x); m=max(m,(peak-x)/peak if peak else 0)
 return m
def hhi(weights): return float(sum(w*w for w in weights))
