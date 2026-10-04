import random

EVENTS={
 'RATE_UP':{'base':-.025,'factor':'rate_sensitivity'},'RATE_DOWN':{'base':.025,'factor':'rate_sensitivity'},
 'OIL_UP':{'base':.045,'factor':'oil_sensitivity'},'OIL_DOWN':{'base':-.045,'factor':'oil_sensitivity'},
 'MARKET_BOOM':{'base':.035,'factor':'sentiment_sensitivity'},'MARKET_CRASH':{'base':-.055,'factor':'sentiment_sensitivity'},
 'GROWTH':{'base':.030,'factor':'growth_sensitivity'},'SLOWDOWN':{'base':-.030,'factor':'growth_sensitivity'},
 'DIVIDEND':{'base':.025,'factor':'dividend_factor'},'SECTOR_SHOCK':{'base':-.035,'factor':'sector_sensitivity'},
}

def response(profile,event_type,round_number,magnitude=None,selected_sector=None,direction=1,severity='MEDIUM'):
 config=EVENTS.get(event_type,{'base':magnitude or .02,'factor':'sentiment_sensitivity'})
 base=(magnitude if magnitude is not None else config['base'])*direction
 if event_type=='CUSTOM': base=abs(base)*direction
 factor_name=config['factor']
 if factor_name=='dividend_factor': factor=1.0 if profile.dividend_characteristic=='Strong' else (.55 if profile.dividend_characteristic=='Regular' else .25)
 else: factor=getattr(profile,factor_name)
 if event_type=='SECTOR_SHOCK' and selected_sector and profile.sector!=selected_sector: factor=.12
 severity_mult={'LOW':.65,'MEDIUM':1.0,'HIGH':1.45}.get(severity.upper(),1.0)
 vol_mult=.80+min(profile.volatility_level,.45)
 rng=random.Random(f'{round_number}:{event_type}:{profile.symbol}')
 noise=rng.uniform(-.0025,.0025)
 change=base*profile.beta*factor*vol_mult*severity_mult+noise
 return max(-.15,min(.15,change))

def generic_stock_response(symbol,event_type,round_number,magnitude=None,direction=1,severity='MEDIUM'):
 bases={'RATE_UP':-.010,'RATE_DOWN':.010,'OIL_UP':.004,'OIL_DOWN':-.004,'MARKET_BOOM':.025,'MARKET_CRASH':-.035,'GROWTH':.015,'SLOWDOWN':-.015,'DIVIDEND':.006,'SECTOR_SHOCK':-.004,'STOCK_SHOCK':magnitude or 0,'MIXED':magnitude or 0,'CUSTOM':abs(magnitude or .01)*direction}
 base=bases.get(event_type,magnitude or 0);severity_mult={'LOW':.7,'MEDIUM':1.0,'HIGH':1.35}.get(severity.upper(),1.0);rng=random.Random(f'legacy:{round_number}:{event_type}:{symbol}');return max(-.10,min(.10,base*severity_mult+rng.uniform(-.0015,.0015)))
