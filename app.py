from flask import Flask
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slackeventsapi import SlackEventAdapter
from slack_tokens import SLACKBOT_TOKEN, SLACK_EVENTS_TOKEN
import logging
# import os
from time import strftime, time, localtime
import pprint
import pyupbit
from upbit_tokens import ACCESS_TOKEN, SECRET_TOKEN

app = Flask(__name__)

upbit = pyupbit.Upbit(ACCESS_TOKEN, SECRET_TOKEN)

slack_events_adapter = SlackEventAdapter(SLACK_EVENTS_TOKEN, "/slack/events", app)
# slack_web_client = WebClient(token=os.environ.get("SLACKBOT_TOKEN"))
slack_web_client = WebClient(token=SLACKBOT_TOKEN)

MESSAGE_BLOCK = {
    "type": "section",
    "text": {
        "type": "mrkdwn",
        "text": "",
    }
}

# Upbit 현재가 및 잔고 조회 위한 전처리
tickers = pyupbit.get_tickers(fiat="KRW")
list_all_price = []
balances_data = []
dict_all_price = {}

# Slack message event 처리
@slack_events_adapter.on("message")
def message(payload):
    event = payload.get("event", {})
    text = event.get("text")
    command = []
    command = text.split()

    # 잔고 확인(Closed API)
    match command:
        case ['!balance']:
            channel_id = event.get("channel")
            try:
                for i in upbit.get_balances():
                    # 잔고가 있는 항목만 출력
                    if float(i['balance']) > 0.01:
                        balances_data.append([i['currency'], i['balance']])
                results = balances_data
            except:
                results = "⚠️ 업비트 API 에러가 발생했습니다. 잠시 후 다시 시도해주세요."

            message = f"🏦 ONE MILLION VC 잔액\n\n {results}"
            MESSAGE_BLOCK["text"]["text"] = message
            message_to_send = {"channel": channel_id, "blocks": [MESSAGE_BLOCK]}

            return slack_web_client.chat_postMessage(**message_to_send)

        # 원화거래 가능한 전체 암호화폐 현재가 조회
        case ["!allprice"]:
            # 가격 조회 직전시간 측정
            tm = time()
            ltm = localtime(tm)
            current_time = strftime('%Y-%m-%d %I:%M:%S %p', ltm)
        
            try:
                dict_all_price = pyupbit.get_current_price(tickers)
                # convert dict to list
                list_all_price = [(k[-3:], str(v)+" 원") for k, v in dict_all_price.items()]
                results = list_all_price
            except:
                results = "⚠️ 업비트 API 에러가 발생했습니다. 잠시 후 다시 시도해주세요."

            channel_id = event.get("channel")
            message = f"📈 전체 암호화폐 현재가\n ({current_time} 기준)\n\n {results}"

            MESSAGE_BLOCK["text"]["text"] = message
            message_to_send = {"channel": channel_id, "blocks": [MESSAGE_BLOCK]}
            return slack_web_client.chat_postMessage(**message_to_send)


        # 특정 암호화폐 현재가 조회
        case ["!price", *other_items]:
            ticker = command[1]
            # 가격 조회 직전시간 측정
            tm = time()
            ltm = localtime(tm)
            current_time = strftime('%Y-%m-%d %I:%M:%S %p', ltm)
            try:
                current_price = pyupbit.get_current_price("KRW-"+ticker)
                channel_id = event.get("channel")
                message = f"🪙 {ticker[-3:].upper()} 현재가: {current_price} 원\n({current_time} 기준)"
            except:
                message = "⚠️ 업비트 API 에러가 발생했습니다. 잠시 후 다시 시도해주세요."

            MESSAGE_BLOCK["text"]["text"] = message
            message_to_send = {"channel": channel_id, "blocks": [MESSAGE_BLOCK]}
            return slack_web_client.chat_postMessage(**message_to_send)

        # 암호화폐 시장가 매수 기능(Closed API)
        case ["!buy", *other_items,]:
            try:
                ticker = str(command[1]).upper()
                # 수수료 0.05% 계산
                price = int(command[2]) * 0.9995
                upbit.buy_market_order("KRW-"+ticker, int(price))
                message = "📢 매수 주문을 입력합니다."
            except:
                message = "⚠️ 알 수 없는 에러가 발생했습니다. 잠시 후 다시 시도해주세요."

            channel_id = event.get("channel")            
            MESSAGE_BLOCK["text"]["text"] = message
            message_to_send = {"channel": channel_id, "blocks": [MESSAGE_BLOCK]}
            return slack_web_client.chat_postMessage(**message_to_send)
        
        # 암호화폐 시장가 매도 기능(Closed API)
        case ["!sell", *other_items]:
            try:
                ticker = str(command[1]).upper()
                amount = float(command[2])

                # 체결되면 수수료 0.05% 계산된 금액이 현금화됨
                upbit.sell_market_order("KRW-"+ticker, amount)
                message = f"📢 매도 주문을 입력합니다."
            except:
                message = "⚠️ 알 수 없는 에러가 발생했습니다. 잠시 후 다시 시도해주세요."

            channel_id = event.get("channel")
            MESSAGE_BLOCK["text"]["text"] = message
            message_to_send = {"channel": channel_id, "blocks": [MESSAGE_BLOCK]}
            return slack_web_client.chat_postMessage(**message_to_send)

        # 도움말
        case ["!help"]:
            channel_id = event.get("channel")
            message = f"도움말 📗\n ❕price BTC: 특정 암호화폐 시세 조회\n\n"\
                      f"❕allprice: 원화거래소 상장 암호화폐 현재가 조회\n\n"\
                      f"❕balance: 잔고 조회(원화 및 암호화폐 보유 개수가 소수점까지 표시됨)\n\n"\
                      f"❕buy BTC **숫자**: 암호화폐 시장가 매수(숫자는 원 단위)\n ex> (느낌표)buy BTC 5000\n\n"\
                      f"❕sell BTC **숫자**: 암호화폐 시장가 매도(숫자는 암호화폐 개수)\n ex> (느낌표)sell BTC 2\n\n"\
                      f"🤖 지정가 매수/매도 등 추가기능 업데이트 예정"\

            MESSAGE_BLOCK["text"]["text"] = message
            message_to_send = {"channel": channel_id, "blocks": [MESSAGE_BLOCK]}
            return slack_web_client.chat_postMessage(**message_to_send)
        
        # case _ :
        #     channel_id = event.get("channel")
        #     message = f"※ 명령어를 잘못 입력했습니다."

        #     MESSAGE_BLOCK["text"]["text"] = message
        #     message_to_send = {"channel": channel_id, "blocks": [MESSAGE_BLOCK]}
        #     return slack_web_client.chat_postMessage(**message_to_send)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)