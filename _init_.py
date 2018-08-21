import requests
import re
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
# Convert Tickers to SEC EDGAR CIK
def getCIKs(tickers):
    URL = 'http://www.sec.gov/cgi-bin/browse-edgar?CIK={}&Find=Search&owner=exclude&action=getcompany'
    CIK_RE = re.compile(r'.*CIK=(\d{10}).*')    
    cikstore = []
    for ticker in tickers:
        f = requests.get(URL.format(ticker), stream = True)
        results = CIK_RE.findall(f.text)
        if len(results):
            cikstore.append(results[0]) 
    return(cikstore)
############################## INPUT COVERAGE LIST #############################
COVERAGE = ['TLGT','TEVA','SLGL','ATRS','PRGO','PLXP','MYL','MNK','LCI','FLXN',
            'ENDP','DERM','AMRX','ANIP','AMPH','AKRX','AGN','AERI','ADMP']
CIKS = getCIKs(COVERAGE)
# Begin loop for every ticker
for i in range(0,len(CIKS)):
    # Parse requests from appropriate url
    url = 'https://www.sec.gov/cgi-bin/own-disp?action=getissuer&CIK={}'\
            .format(CIKS[i])
    response = requests.get(url).text
    soup = BeautifulSoup(response,"lxml")
    rows = soup.find_all('tr')
    # Get and edit hyperlinks to Form 4 documents
    links = []
    for link in soup.find_all('a',href=True):
        links.append(link['href'])
    del links[-3:]
    links = links[-80:]
    links = ['https://www.sec.gov'+ s for s in links] 
    start = -1 
    # Get first table
    df1 = pd.DataFrame(columns = ['Reporting Owner','Filings','Transaction Date',
                                    'Type of Owner'])
    # Find start and stop points in the xml 
    for row in rows:
        cols = row.find_all('td')
        cols = [x.text.strip() for x in cols]
        start = start + 1
        if cols == ['Owner', 'Filings', 'Transaction Date', 'Type of Owner']:
            startmark = start
        if cols == []:
            endmark = start-1
    start = -1
    # Scrape and save appropriate data to df
    for row in rows:
        cols = row.find_all('td')
        cols = [x.text.strip() for x in cols]
        start = start + 1
        try:
            if start>startmark and start<=endmark:
                df1.loc[start] = cols
            else:
                pass
        except NameError:
            pass
    # Get second table
    df2 = pd.DataFrame(columns = ['Acquisition/Disposition','Transaction Date',
                                  'Deemed Execution Date','Reporting Owner',
                                  'Form Link','Transaction Type',
                                  'Direct/Indirect Ownership',
                                  '# Securities Transacted','# Securities Owned',
                                  'Owner Title','Owner CIK','Security Name'])
    start = -1
    # Scrape and save appropriate data to df
    for row in rows:
        cols = row.find_all('td')
        cols = [x.text.strip() for x in cols]
        start = start + 1
        try:
            if start>(endmark+1) and start<(len(rows)-1):
                df2.loc[start] = cols
            else:
                pass
        except NameError:
            pass
    df2['Form Link'] = links # replace Form 4 with URL
    # VLOOKUP function to combine dataframes with Type of Owner info
    officertitle = []
    for j in range(0,len(df2.index)):
        vlookup = df1.index[df1['Reporting Owner'] == df2['Reporting Owner'].iloc[j]].tolist()
        officertitle.append(df1.loc[vlookup,'Type of Owner'].to_string())
    officertitle = [s[6:] for s in officertitle] # formatting
    df2['Owner Title'] = officertitle # add owner title to df
    # Reorganize dataframe to better match Form 4 layout
    df3 = df2[['Reporting Owner','Owner Title','Security Name',
              'Transaction Date','Transaction Type', '# Securities Transacted',
              'Acquisition/Disposition', 'Deemed Execution Date',
              '# Securities Owned','Direct/Indirect Ownership','Owner CIK',
              'Form Link',]]
    # Get rid of not helpful columns
    del df3['Deemed Execution Date']
    del df3['Owner CIK']
    print(df3)
    # Save DF to excel
    writer = pd.ExcelWriter(COVERAGE[i]+'insiders.xlsx')
    df3.to_excel(writer,'Transactions',index=False)
    writer.save()
