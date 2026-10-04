PSX_STOCKS = [
 {'symbol':'UBL','name':'United Bank Limited','sector':'Commercial Banking','price':425.0,'volatility':.23,'risk_level':'Medium','dividend':'Regular','beta':1.10,'rate_sensitivity':1.00,'oil_sensitivity':.08,'growth_sensitivity':.75,'sentiment_sensitivity':.80,'sector_sensitivity':.90},
 {'symbol':'EFERT','name':'Engro Fertilizers Limited','sector':'Fertilizer','price':205.0,'volatility':.17,'risk_level':'Low-Medium','dividend':'Strong','beta':.72,'rate_sensitivity':.30,'oil_sensitivity':-.10,'growth_sensitivity':.42,'sentiment_sensitivity':.48,'sector_sensitivity':.65},
 {'symbol':'NRL','name':'National Refinery Limited','sector':'Refinery','price':596.0,'volatility':.39,'risk_level':'High','dividend':'Variable','beta':1.38,'rate_sensitivity':.30,'oil_sensitivity':1.00,'growth_sensitivity':.72,'sentiment_sensitivity':1.00,'sector_sensitivity':1.00},
 {'symbol':'ATRL','name':'Attock Refinery Limited','sector':'Refinery','price':490.0,'volatility':.36,'risk_level':'High','dividend':'Variable','beta':1.30,'rate_sensitivity':.28,'oil_sensitivity':.90,'growth_sensitivity':.68,'sentiment_sensitivity':.92,'sector_sensitivity':.95},
 {'symbol':'POL','name':'Pakistan Oilfields Limited','sector':'Oil & Gas Exploration','price':755.0,'volatility':.29,'risk_level':'Medium-High','dividend':'Strong','beta':.94,'rate_sensitivity':.18,'oil_sensitivity':.88,'growth_sensitivity':.55,'sentiment_sensitivity':.68,'sector_sensitivity':.88},
 {'symbol':'APL','name':'Attock Petroleum Limited','sector':'Oil Marketing','price':510.0,'volatility':.24,'risk_level':'Medium','dividend':'Strong','beta':.86,'rate_sensitivity':.22,'oil_sensitivity':.55,'growth_sensitivity':.70,'sentiment_sensitivity':.62,'sector_sensitivity':.78},
]

CORRELATIONS = {
 ('ATRL','NRL'):.82, ('APL','POL'):.62, ('APL','ATRL'):.58, ('APL','NRL'):.55,
 ('ATRL','POL'):.66, ('NRL','POL'):.68, ('EFERT','UBL'):.28,
}

def correlation(left,right):
 if left==right:return 1.0
 return CORRELATIONS.get(tuple(sorted((left,right))),.20)
