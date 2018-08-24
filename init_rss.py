import requests
import re
from bs4 import BeautifulSoup
import pandas as pd
import time
import pickle
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import formatdate
from email import encoders
############################## INPUT COVERAGE LIST #############################
COVERAGE = ['TLGT','TEVA','SLGL','ATRS','PRGO','PLXP','MYL','MNK','LCI','FLXN',
            'ENDP','DERM','AMRX','ANIP','AMPH','AKRX','AGN','AERI','ADMP']
youremail = 'vikram.arun95@gmail.com'
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
# Function to get 4k from CIK Code
def parse4(CIKcodes):
    for i in range(0,len(CIKcodes)):
            # Parse requests from appropriate url
            url = 'https://www.sec.gov/cgi-bin/own-disp?action=getissuer&CIK={}'\
                    .format(CIKcodes[i])
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
            newlinks = link2form(links)
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
            df2['Form Link'] = newlinks # replace Form 4 with edited urls
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
            # Format columns
            df3['# Securities Transacted'] = pd.to_numeric(df3['# Securities Transacted'],downcast='signed')
            df3['# Securities Owned'] = pd.to_numeric(df3['# Securities Owned'],downcast='signed')
            df3['Direct/Indirect Ownership'] = df3['Direct/Indirect Ownership'].str[2:]
            df3['Owner Title'] = df3['Owner Title'].str.title()
            # Get rid of not helpful columns
            del df3['Deemed Execution Date']
            del df3['Owner CIK']
            # Save DF to excel
            ref = CIKS.index(CIKcodes[i])
            writer = pd.ExcelWriter(COVERAGE[ref]+' Insider Activity.xlsx', engine='xlsxwriter')
            df3.to_excel(writer,'Transactions',index=False)
            worksheet = writer.sheets['Transactions']
            # Set column widths
            worksheet.set_column('A:A',25)
            worksheet.set_column('B:B',45)
            worksheet.set_column('C:C',45)
            worksheet.set_column('D:D',16)
            worksheet.set_column('E:E',16)
            worksheet.set_column('F:F',21)
            worksheet.set_column('G:G',22)
            worksheet.set_column('H:H',18)
            worksheet.set_column('I:I',24)
            worksheet.set_column('J:J',95)
            # Make Hyperlinks
            fill = 0
            for h in range(2,len(df3.index)):
                worksheet.write_url('J'+str(h), newlinks[fill])
                fill = fill+1
            writer.save()
            try:
                if df3['Acquisition/Disposition'].iloc[0] == 'A':
                    text =  df3['Owner Title'].iloc[0] + ' acquires ' + str(df3['# Securities Transacted'].iloc[0]) + ' of ' + df3['Security Name'].iloc[0] + ". More info here: " + df3['Form Link'].iloc[0]
                if df3['Acquisition/Disposition'].iloc[0] == 'D':
                    text =  df3['Owner Title'].iloc[0] + ' disposes ' + str(df3['# Securities Transacted'].iloc[0]) + ' of ' + df3['Security Name'].iloc[0] + ". More info here: " + df3['Form Link'].iloc[0]
                print(text)
                send_mail(youremail,COVERAGE[ref]+' Insider Update',
                          text,
                          open(COVERAGE[ref]+' Insider Activity.xlsx', "rb").read(),
                          COVERAGE[ref]+' Insider Activity.xlsx')
            except IndexError or AttributeError:
                send_mail(youremail,COVERAGE[ref]+' Insider Update',
                          'Error occured, check SEC EDGAR source filing',
                          open(COVERAGE[ref]+' Insider Activity.xlsx', "rb").read(),
                          COVERAGE[ref]+' Insider Activity.xlsx')
            print(COVERAGE[ref]+' initial download done')
def link2form(urllinks):
    try:
        newlinks = []
        for l in range(0,len(urllinks)):
            url = urllinks[l]
            links = []
            response = requests.get(url).text
            soup = BeautifulSoup(response,"lxml")
            for link in soup.find_all('a',href=True):
                links.append(link['href'])
            newlinks.append(links[8])
        newlinks = ['https://www.sec.gov'+ s for s in newlinks]
        return newlinks
    except requests.exceptions.InvalidURL:
        pass
def send_mail(send_to,subject,text,files,filename):
    msg = MIMEMultipart()
    msg['From'] = 'form4updates@gmail.com'
    msg['To'] = send_to
    msg['Date'] = formatdate(localtime = True)
    msg['Subject'] = subject
    msg.attach(MIMEText(text))
    part = MIMEBase('application', "octet-stream")
    part.set_payload(files)
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment; filename='+filename)
    msg.attach(part)
    smtp = smtplib.SMTP('smtp.gmail.com',587)
    smtp.ehlo()
    smtp.starttls()
    smtp.login('form4updates@gmail.com','iloveinsidertrading')
    smtp.sendmail('form4updates@gmail.com', send_to, msg.as_string())
    smtp.quit()
# Begin continuous loop
CIKS = getCIKs(COVERAGE)
count = 1
while True:
    # The first time it's run, need to initialize all the data files
    if count == 1:
        parse4(CIKS)
        print('All initial downloads are done! Will continue to update...')
        count = count + 1
    # After that, we only parse the RSS feed instead (won't get blocked that way)
    else:
        # Start scraping RSS feed
        url = 'http://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=only&start=0&count=100&output=atom'
        response = requests.get(url).text
        soup = BeautifulSoup(response,"lxml")
        rows = soup.find_all('title')
        # Get CIKS on the RSS Feed
        newCIKS = []
        for row in rows:
            newCIKS.append(re.findall('\d+',row.text)[1])
        newCIKS = newCIKS[1:] # remove year from numbers scraped
        try:
            # Load recent CIKS file
            with open ('rss', 'rb') as fp:
                oldCIKS = pickle.load(fp)
            if oldCIKS == newCIKS:
                print('No updates')
            # See if anything new in the RSS feed is significant to our coverage
            else:
                tickerstoupdate = list(set(CIKS).intersection(newCIKS))
                if tickerstoupdate: # significant change, update files
                    print(tickerstoupdate)
                    parse4(tickerstoupdate)
                if not tickerstoupdate: # not significant, pass
                    print('Something not in coverage updated')
                # Update CIKS file because it is different
                with open('rss', 'wb') as fp:
                    pickle.dump(newCIKS, fp)
        # Catch exception the first time this is run and create the file
        except FileNotFoundError:
            with open('rss', 'wb') as fp:
                pickle.dump(newCIKS, fp)
        # Loop forever with a pause
        time.sleep(60)
