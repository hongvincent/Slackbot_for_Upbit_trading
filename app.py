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
orders_data = []
order_status = []

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
            try:
                balances_data.clear()
                for i in upbit.get_balances():
                    # 잔고가 있는 항목만 출력
                    if float(i['balance']) > 0.00001:
                        balances_data.append([i['currency'], i['balance']])
                results = balances_data
            except:
                results = "⚠️ 업비트 API 에러가 발생했습니다. 잠시 후 다시 시도해주세요."
            
            channel_id = event.get("channel")
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
                price = int(command[2])
                upbit.buy_market_order("KRW-"+ticker, int(price))
                time.sleep(3)
                buy_done_ret = upbit.get_order("KRW-"+ticker, state="done")
                message = f"📢 매수 주문을 입력했습니다.\n\n {buy_done_ret}"
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
                time.sleep(3)
                sell_done_ret = upbit.get_order("KRW-"+ticker, state="done")
                message = f"📢 매도 주문을 입력했습니다.\n\n {sell_done_ret}"
            except:
                message = "⚠️ 알 수 없는 에러가 발생했습니다. 잠시 후 다시 시도해주세요."

            channel_id = event.get("channel")
            MESSAGE_BLOCK["text"]["text"] = message
            message_to_send = {"channel": channel_id, "blocks": [MESSAGE_BLOCK]}
            return slack_web_client.chat_postMessage(**message_to_send)
        
        # 암호화폐 지정가 매수 기능(Closed API)
        case ["!limitbuy", *other_items]:
            try:
                ticker = str(command[1]).upper()
                price = float(command[2])
                # 매수 수량
                volume = float(command[3])
                lbuy_order_ret = upbit.buy_limit_order("KRW-"+ticker, price, volume)
                message = f"📢 매수 주문을 입력했습니다.\n\n {lbuy_order_ret}"
            except:
                message = "⚠️ 알 수 없는 에러가 발생했습니다. 잠시 후 다시 시도해주세요."

            channel_id = event.get("channel")            
            MESSAGE_BLOCK["text"]["text"] = message
            message_to_send = {"channel": channel_id, "blocks": [MESSAGE_BLOCK]}
            return slack_web_client.chat_postMessage(**message_to_send)
        
        # 암호화폐 지정가 매도 기능(Closed API)
        case ["!limitsell", *other_items]:
            try:
                ticker = str(command[1]).upper()
                price = int(command[2])
                # 매도 수량
                volume = int(command[3])
                lsell_order_ret = upbit.sell_limit_order("KRW-"+ticker, price, volume)
                message = f"📢 매도 주문을 입력했습니다.\n\n {lsell_order_ret}"
            except:
                message = "⚠️ 알 수 없는 에러가 발생했습니다. 잠시 후 다시 시도해주세요."

            channel_id = event.get("channel")            
            MESSAGE_BLOCK["text"]["text"] = message
            message_to_send = {"channel": channel_id, "blocks": [MESSAGE_BLOCK]}
            return slack_web_client.chat_postMessage(**message_to_send)

        # 미체결 지정가 주문 현황 조회(Closed API)
        case ['!orders', *other_items]:
            try:
                ticker = str(command[1]).upper()
                order_status = []
                order_status = upbit.get_order("KRW-"+ticker, state="wait")
                results = order_status
            except:
                results = "⚠️ 업비트 API 에러가 발생했습니다. 잠시 후 다시 시도해주세요."

            channel_id = event.get("channel")
            message = f"🔜미체결 주문 현황\n\n {results}"
            MESSAGE_BLOCK["text"]["text"] = message
            message_to_send = {"channel": channel_id, "blocks": [MESSAGE_BLOCK]}
            return slack_web_client.chat_postMessage(**message_to_send)

        # 직전 미체결 지정가 주문 취소(Closed API)
        case ['!cancle', *other_items]:
            try:
                ticker = str(command[1]).upper()
                r = upbit.get_order("KRW-"+ticker)
                if len(r) > 0:
                    cancle_data = upbit.cancel_order(r[0]['uuid'])
                results = cancle_data
                check_calnce_order = upbit.get_order("KRW-"+ticker, state="cancel")
            except:
                results = "⚠️ 업비트 API 에러가 발생했습니다. 잠시 후 다시 시도해주세요."

            channel_id = event.get("channel")
            message = f"❎주문을 취소했습니다.\n\n {results} \n\n 🟢취소상태(state) 확인\n\n{check_calnce_order[0]}"
            MESSAGE_BLOCK["text"]["text"] = message
            message_to_send = {"channel": channel_id, "blocks": [MESSAGE_BLOCK]}
            return slack_web_client.chat_postMessage(**message_to_send)

        # 도움말
        case ["!help"]:
            channel_id = event.get("channel")
            message = f"도움말 📗\n ❕price BTC: 특정 암호화폐 시세 조회\n\n"\
                      f"❕allprice: 원화거래소 상장 암호화폐 현재가 조회\n\n"\
                      f"❕balance: 잔고 조회(원화 및 암호화폐 보유 개수가 소수점까지 표시됨)\n\n"\
                      f"❕buy *티커* *원*: 암호화폐 시장가 매수(매수 전 잔고내 현금 확인)\n ex> (느낌표)buy BTC 5000\n\n"\
                      f"❕sell *티커* *수량*: 암호화폐 시장가 매도(매도 전 잔고내 보유량 확인)\n ex> (느낌표)sell BTC 0.02\n\n"\
                      f"❕limitbuy *티커* *원* *수량*: 암호화폐 지정가 매수(매수 전 잔고내 현금 확인)\n ex> (느낌표)limitbuy BTC 30000000 0.0002\n\n"\
                      f"❕limitsell *티커* *원* *수량*: 암호화폐 지정가 매도(매도 전 잔고내 보유량 확인)\n ex> (느낌표)limitsell BTC 50000000 0.01\n\n"\
                      f"❕orders: 미체결 지정가 주문 현황 조회\n ex> (느낌표)orders BTC\n\n"\
                      f"❕cancle: 직전 미체결 지정가 주문 취소\n ex> (느낌표)cancle BTC\n\n"\

            MESSAGE_BLOCK["text"]["text"] = message
            message_to_send = {"channel": channel_id, "blocks": [MESSAGE_BLOCK]}
            return slack_web_client.chat_postMessage(**message_to_send)
        
        # case _ :
        #     channel_id = event.get("channel")
        #     message = f"※ 명령어를 잘못 입력했습니다. 다시 입력해주세요."

        #     MESSAGE_BLOCK["text"]["text"] = message
        #     message_to_send = {"channel": channel_id, "blocks": [MESSAGE_BLOCK]}
        #     return slack_web_client.chat_postMessage(**message_to_send)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
