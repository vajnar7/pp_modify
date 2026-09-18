# skripta vpiše alokacije in prognoze z REST iz plinovodov v tabelo zp_alokacije - za kasnejši obračun
# plinski dan je trenutni datum vedno zmanjsan za en mesec (25 dni)

import os
import sys
import argparse
import configparser
import pandas as pd
import requests
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo  # Python 3.9+
import mysql.connector
import pyodbc
import ssl
from urllib3.poolmanager import PoolManager
from requests.adapters import HTTPAdapter
import calendar

# === CONFIG LOAD ===
config = configparser.ConfigParser()
config.read('param.ini')

# DB podatki 
dbhost = config['DB']['host']
dbuser = config['DB']['user']
dbpassword = config['DB']['password']
dbdatabase = config['DB']['database']

okolje = config['API']['okolje']

class UnsafeTLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        self.poolmanager = PoolManager(*args, ssl_context=ctx, **kwargs)

session = requests.Session()
session.mount('https://', UnsafeTLSAdapter())

# API podatki
if okolje == 'TEST':
    baseUrl = config['API']['baseUrlTest']
    print('PAZI!!!   TESTNO okolje **************************')
else:
    baseUrl = config['API']['baseUrl']

dns = config['DB41']['ODBCDNS']

cert_path = (
    config['CERT']['cert_file'],
    config['CERT']['key_file']
)

connection = pyodbc.connect(f'DSN={dns}')

# argumenti
parser = argparse.ArgumentParser()
parser.add_argument("-d", "--datum", type=datetime.fromisoformat, help="plinski dan (YYYY-MM-DD)")
parser.add_argument("-cg", help="CityGate")
args = parser.parse_args()

#kateri datum
selected_date = args.datum.date() if args.datum else datetime.now().date()-timedelta(days=25)

date_str = selected_date.strftime("%Y-%m-%d")

url = f'{baseUrl}/v1/PpWs/GetOfftakePointsAllocations'

def preberi_in_napolni(kaj='IncludeNotDailyMeasuredForecastsOnly',citygate='2904003'):
    payload = {
    "query": {
        "periodStart": f"{date_str}",
        "options": f"{kaj}"
    }
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Cache-Control": "no-cache",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "User-Agent": "PostmanRuntime/7.44.1"
    }

    response = session.post(url, json=payload, headers=headers, cert=cert_path)
    #response = requests.post(url, cert=cert_path)

    if response.status_code != 200:
        raise RuntimeError(f"❌ Poizvedba ni uspešna!: {response.status_code} {response.text}")
        sys.exit(0)

    #beri podatke s PP
    data = response.json()
    #print("Status:", response.status_code)
    #print("Headers:", response.headers)
    #print("Body:", response.text)
    print(f"Za plinski dan: {date_str}")

    items_list = data.get('Allocations',[])

    i = 0

    for item in items_list:
        # preskoči če ni pravi gate
        GasDay = datetime.fromisoformat(item['GasDay']).date()
#        GasDay = item['GasDay'].date()
        OfftakePointCode = item['OfftakePointCode']
        CityGateCode = item['CityGateCode']

        i += 1

        if (i % 1000) == 0:
            print(i)

        if CityGateCode != citygate: 
            continue

        if kaj == 'IncludeNotDailyMeasured':
            Quantity = item['Quantity']
            sql = f"""
                INSERT INTO zp_alokacije set kdaj="{GasDay}", om="{OfftakePointCode}" ,cgate="{CityGateCode}",kolicina={Quantity}
                ON DUPLICATE KEY UPDATE kolicina={Quantity}
            """
            cursorW.execute(sql)
        elif kaj == "IncludeNotDailyMeasuredForecastsOnly":
            QuantityProg = item['Quantity']
            sql = f"""
                INSERT INTO zp_alokacije set kdaj="{GasDay}", om="{OfftakePointCode}" ,cgate="{CityGateCode}", prognozirana={QuantityProg}
                ON DUPLICATE KEY UPDATE prognozirana={QuantityProg}
            """
            cursorW.execute(sql)
        if kaj == 'IncludeDailyMeasured':
            Quantity = item['Quantity']
            sql = f"""
                INSERT INTO zp_alokacije set kdaj="{GasDay}", om="{OfftakePointCode}" ,cgate="{CityGateCode}",kolicina={Quantity}
                ON DUPLICATE KEY UPDATE kolicina={Quantity}
            """
            cursorW.execute(sql)

    connection.commit()

### MAIN ###
# brisi podatke za obdobje in citygate
first_day = selected_date.replace(day=1)
last_day = selected_date.replace(day=calendar.monthrange(selected_date.year, selected_date.month)[1])
sql = f"delete from zp_alokacije where kdaj between\"{first_day}\" and \"{last_day}\"  "
cursorW = connection.cursor()
cursorW.execute(sql)
connection.commit()

#vpiši
preberi_in_napolni('IncludeNotDailyMeasured','2904003')
preberi_in_napolni('IncludeNotDailyMeasuredForecastsOnly','2904003')
preberi_in_napolni('IncludeNotDailyMeasured','2905004')
preberi_in_napolni('IncludeNotDailyMeasuredForecastsOnly','2905004')
# še dnevno merjeni jesenice - samo odčitki brez prognoze
preberi_in_napolni('IncludeDailyMeasured','2905004')






