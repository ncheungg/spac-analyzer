from typing import List, Tuple
import requests
import xml.etree.ElementTree as ET
import dataclasses
from datetime import datetime
from bs4 import BeautifulSoup
import re


@dataclasses.dataclass
class SPAC:
    name: str
    ticker: str
    date: str
    link: str
    link_content: bytes


def get_all_recent_listings() -> ET:
    res = requests.get('https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&CIK=&type=S-1&company=&dateb=&owner=include&start=0&count=100&output=atom', headers={"User-Agent": "Mozilla/5.0"})
    data = res.text

    return ET.fromstring(data)


def get_ciks_from_xml(xml: ET) -> Tuple[str]:
    entries = [child for child in xml if child.tag == '{http://www.w3.org/2005/Atom}entry']
    links = [child for entry in entries for child in entry if child.tag == '{http://www.w3.org/2005/Atom}link']
    hrefs = [link.attrib['href'] for link in links]
    ciks: List[str] = [href.split('/')[6] for href in hrefs]

    return tuple(ciks)


def get_potential_spacs_from_cik(cik: str) -> Tuple[SPAC]:
    res = requests.get(f'https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json', headers={"User-Agent": "Mozilla/5.0"})
    data = res.json()

    filings = data['filings']['recent']

    access_numbers = filings['accessionNumber']
    forms = filings['form']
    primary_documents = filings['primaryDocument']
    filing_dates = filings['filingDate']

    potential_spacs: List[SPAC] = []

    for access_number, form, primary_document, filing_date in zip(access_numbers, forms, primary_documents, filing_dates):
        if 'S-1' in form:
            spac = SPAC(
                name='',
                ticker='',
                date=datetime.strptime(filing_date, '%Y-%m-%d').strftime('%B %d, %Y'),
                link=f'https://www.sec.gov/Archives/edgar/data/{cik}/{access_number.replace("-", "")}/{primary_document}',
                link_content=b''
            )
            potential_spacs.append(spac)

    return tuple(potential_spacs)


def fetch_filing_document(spac: SPAC) -> None:
    res = requests.get(spac.link, headers={"User-Agent": "Mozilla/5.0"})
    spac.link_content = res.content


def is_spac(spac: SPAC) -> bool:
    return b'blank check company' in spac.link_content
        

def add_name_to_spac(spac: SPAC) -> None:
    soup = BeautifulSoup(spac.link_content, 'lxml')
    element = soup.find('p', {'style': 'margin-top:6pt; margin-bottom:0pt; font-size:22pt; font-family:Times New Roman'})

    if element is None:
        return

    name = element.text
    name = name.strip().replace('\n', ' ')
    spac.name = name


def add_ticker_to_spac(spac: SPAC) -> None:
    soup = BeautifulSoup(spac.link_content, 'lxml')
    tickers = []

    elements = []
    elements.extend(soup.findAll('p', string=re.compile('under the symbol')))
    elements.extend(soup.findAll('p', string=re.compile('under the new ticker symbol')))

    for element in elements:
        words = element.text.split()

        for i in range(4, len(words) - 1):
            if words[i - 4:i + 1] == ['under', 'the', 'new', 'ticker', 'symbols']:
                tickers.append(words[i + 1][1:-1])
            if words[i - 4:i + 1] == ['under', 'the', 'new', 'ticker', 'symbol']:
                tickers.append(words[i + 1][1:-1])
            if words[i - 2:i + 1] == ['under', 'the', 'symbols']:
                tickers.append(words[i + 1][1:-1])
            if words[i - 2:i + 1] == ['under', 'the', 'symbol']:
                tickers.append(words[i + 1][1:-1])

    # for element in elements:
    #     words = element.split()
    #     tickers.extend(re.findall('\\x93([^\\x94]+)\\x94', element.text))

    tickers.sort(key=len)

    if tickers:
        spac.ticker = tickers[0]


def send_post_request(spacs: List[SPAC]) -> None:
    body = {
        'data': [dataclasses.asdict(spac) for spac in spacs]
    }

    print(body)
    res = requests.post('https://coe892-project-server.onrender.com/spacs', json=body)


if __name__ == '__main__':
    xml = get_all_recent_listings()
    ciks = get_ciks_from_xml(xml)

    potential_spacs = []
    actual_spacs = []

    for cik in ciks:
        spacs = get_potential_spacs_from_cik(cik)
        potential_spacs.extend(spacs)

    for spac in potential_spacs:
        fetch_filing_document(spac)
        
        if not is_spac(spac):
            continue
        
        add_name_to_spac(spac)
        add_ticker_to_spac(spac)
        actual_spacs.append(spac)

    send_post_request(actual_spacs)
