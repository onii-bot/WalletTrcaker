import requests
import time
from discord_webhook import DiscordWebhook, DiscordEmbed
from pymongo import MongoClient
import os

# Importing Database
cluster = MongoClient(os.environ["MONGO_API"])
db = cluster["discord"]
collection = db["config"]

# Replace the following variables with your own API key and list of addresses to monitor
ETHERSCAN_API_KEY = os.environ["ETHERSCAN_API"]
ADDRESS_LIST = collection.find_one({"_id": 0})['wallets']

# Define the function names to monitor
FUNCTIONS = ['contribute']

# Discord webhook URL
WEBHOOK_URL = os.environ["WEBHOOK"]

def send_discord_webhook_embed(tx, nickname):
    eth_value = float(tx['value']) / 1e18  # Convert value from wei to ETH
    transaction_link = f'https://etherscan.io/tx/{tx["hash"]}'
    message = f'{nickname} minted {eth_value:.6f}Ξ on contract 0x....\n'
    webhook = DiscordWebhook(url=WEBHOOK_URL)
    embed = DiscordEmbed(color=000000,title=message)
    embed.add_embed_field(name='Transaction', value=f'[View on Etherscan]({transaction_link})', inline=False)
    webhook.add_embed(embed)
    response = webhook.execute()

# Keep track of processed transaction hashes to avoid duplicate printing
processed_txs = set()
last_checked_txs = {}
c = 0

# Populate processed_txs with the hashes of all transactions that have already been processed
for address in ADDRESS_LIST:
    url = f'https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=desc&apikey={ETHERSCAN_API_KEY}'
    response = requests.get(url)
    tx_list = response.json()['result']
    for tx in tx_list:
        processed_txs.add(tx['hash'])
    last_checked_txs[address] = tx_list[0]['hash'] if tx_list else None

def check_transactions(address):
    global processed_txs
    global last_checked_txs
    url = f'https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=desc&apikey={ETHERSCAN_API_KEY}'
    response = requests.get(url)
    tx_list = response.json()['result']
    last_checked_tx = last_checked_txs[address]
    for tx in tx_list:
        if tx['hash'] == last_checked_tx:
            break
        if tx['hash'] not in processed_txs:
            for function_name in FUNCTIONS:
                if function_name in tx['input'].lower() or (tx.get('functionName') and function_name in tx['functionName'].lower()):
                    eth_value = float(tx['value'])/1e18  # Convert value from wei to ETH
                    print(f'{function_name} function called by {tx["from"]} on contract {tx["to"]} with transaction hash {tx["hash"]} using {eth_value:.6f} ETH')
                    datas = collection.find_one({"_id": 0})
                    nickname = datas["wallets"][tx["from"].lower()]
                    send_discord_webhook_embed(tx, nickname)
            processed_txs.add(tx['hash'])
    last_checked_txs[address] = tx_list[0]['hash'] if tx_list else None


while True:
    ADDRESS_LIST = collection.find_one({"_id": 0})['wallets']
    print(ADDRESS_LIST)
    for address in ADDRESS_LIST:
        # Check if the wallet address is already present in last_checked_txs
        if address not in last_checked_txs:
            # Initialize entry with the latest transaction hash for the wallet
            url = f'https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=desc&apikey={ETHERSCAN_API_KEY}'
            response = requests.get(url)
            tx_list = response.json()['result']
            last_checked_txs[address] = tx_list[0]['hash'] if tx_list else None
        check_transactions(address)
        c += 1
    if c > 4:
        time.sleep(1)
        c = 0
