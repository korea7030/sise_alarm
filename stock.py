import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np
import telegram
import json

BASE_URL = 'https://finance.naver.com/sise/sise_market_sum.nhn?sosok='
START_PAGE = 1
KOSPI_CODE = 0
KOSDAK_CODE = 1

def main(code):
    res = requests.get('{}{}{}'.format(BASE_URL, str(code), '&page={}'.format(START_PAGE)))
    if res.status_code == 200:
        soup = BeautifulSoup(res.text, 'lxml')

        # total page num
        total_page_num = soup.select_one('td.pgRR > a')
        total_page_num = int(total_page_num.get('href').split('=')[-1])

        # query fields
        ipt_html = soup.select_one('div.subcnt_sise_item_top')
        fields = [item.get('value') for item in ipt_html.select('input') 
                if item.get('value') in ['per', 'pbr', 'roe', 'market_sum', 'property_total', 'debt_total', 'sales', 'reserve_ratio', 'listed_stock_cnt']]

        results = [ sise_crawl(code, page, fields) for page in range(1, total_page_num+1)]
        df = pd.concat(results, axis=0, ignore_index=True)
        df.to_excel('result.xlsx', index=False)

        # load data
        pd_result = pd.read_excel('result.xlsx')
        pd_result = pd_result.dropna()
        # BPS
        pd_result['BPS'] = pd_result['현재가'] / pd_result['PBR']
        # 부채비율
        pd_result['부채비율'] = (pd_result['부채총계']/pd_result['자산총계']) * 100
        # PER x PBR 
        pd_result['PER x PBR'] = pd_result['PER'] * pd_result['PBR']
        # 1/PER
        pd_result['1/PER'] = 1/pd_result['PER'].astype(float)
        # BPR
        pd_result['BPR'] = 1/pd_result['PBR'].astype(float)
        # RANK BPR
        pd_result['RANK_BPR'] = pd_result['BPR'].rank(method='max', ascending=False)
        # RANK_1/PER
        pd_result['RANK_1/PER'] = pd_result['1/PER'].rank(method='max', ascending=False)
        # RANK_VALUE
        pd_result['RANK_VALUE'] = (pd_result['RANK_BPR'] + pd_result['RANK_1/PER']) / 2
        # 정렬
        pd_result = pd_result.sort_values(by=['RANK_VALUE'])
        pd_result.to_excel('result_data.xlsx', index=False)

        # send_telegram(pd_result['종목명'][:20])



def sise_crawl(code, page, fields):
    data = {
        'menu': 'market_sum',
        'returnUrl': '{}{}{}'.format(BASE_URL, str(code), '&page={}'.format(page)),
        'fieldIds': fields
    }

    finance_res = requests.post('https://finance.naver.com/sise/field_submit.nhn', data=data)
    finance_res.encoding = 'euc-kr'

    soup = BeautifulSoup(finance_res.text, 'lxml')
    table_html = soup.select_one('table.type_2')

    # column
    header_data = [item.get_text().strip() for item in table_html.find('thead').find('tr').find_all('th') if item.get_text().strip() not in ['전일비', '등락률']]
    del header_data[-1]

    # data
    td_items = [tr_item.find_all('td') for tr_item in table_html.find('tbody').find_all('tr')][1:]

    # 내부 데이터
    # inner_data = [i.get_text().strip().replace(',', '') for item in td_items for i in item 
    #     if (i.find('a') or len(i.get('class', [])) > 0 or i.get('class', []) in ['no', 'number']) and i.get_text().strip() != '' ]
    inner_data = []
    for item in td_items:
        for i in item[0:len(item)-1]:
            if i.find('a') or len(i.get('class', [])) > 0:
                child = i.findChildren()
                if len(child) >= 1:
                    if child[0].get('href'):
                        inner_data.append(child[0].get_text().strip())
                else:
                    inner_data.append(i.get_text().strip().replace(',', ''))

    # 번호 데이터
    no_data = [i.get_text().strip() for item in td_items for i in item if len(i.get('class', [])) > 0 and ('no' in i.get('class', []))]

    number_data = np.array(inner_data)
    number_data.resize(len(no_data), len(header_data))
    df = pd.DataFrame(data=number_data, columns=header_data)

    return df


def send_telegram(data):
    with open('token.json', 'r') as f:
        json_data = json.loads(f.read())
        token = json_data['token']
        bot = telegram.Bot(token=token)
        chat_id = 1752949298
        bot.sendMessage(chat_id=chat_id, text=data)


if __name__ == '__main__':
    main(KOSPI_CODE)