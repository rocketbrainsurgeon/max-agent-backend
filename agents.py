import os
import json
from dotenv import load_dotenv
from swarm import Agent
from web3 import Web3
from eth_account import Account
from eth_account.signers.local import LocalAccount

provider_url: str = 'http://127.0.0.1:8545'
# provider_url: str = 'https://rpc.ankr.com/base_sepolia/3ec8a99c8d8a9f1d4b41cbbd6849bd882e7af57f597634fd1f39c6cb5986656f'
# provider_url: str = 'https://rpc.ankr.com/bsc_testnet_chapel/3ec8a99c8d8a9f1d4b41cbbd6849bd882e7af57f597634fd1f39c6cb5986656f'

w3 = Web3(Web3.HTTPProvider(provider_url))

with open('tokens.json') as f:
    tokens = json.load(f)['tokens']


def load_wallet() -> LocalAccount:
    # Load .env file
    if not load_dotenv():
        raise FileNotFoundError("The .env file is missing.")

    # Retrieve the PRIVATE_KEY
    private_key = os.getenv("PRIVATE_KEY")

    if not private_key:
        raise ValueError("PRIVATE_KEY is missing in the .env file.")

    account: LocalAccount = Account.from_key(private_key)

    return account

# Usage
wallet = load_wallet()

# Request funds from the faucet (only works on testnet)
# faucet = agent_wallet.faucet()
# print(f"Faucet transaction: {faucet}")
# print(f"Agent wallet address: {agent_wallet.default_address.address_id}")


def load_abi(file_path: str):
    with open(file_path, 'r') as file:
        return json.load(file)


def send_eth(
    sender_account,
    recipient_address,
    amount_eth,
    gas_price_gwei
):
    """
    Sends ETH (base currency of a chain) from a sender account to a recipient address.

    Args:
        sender_account (LocalAccount): The account sending the ETH.
        recipient_address (str): The address to send ETH to.
        amount_eth (float): The amount of ETH to send.
        gas_price_gwei (int): The gas price in Gwei (default: 50).

    Returns:
        HexBytes: The transaction hash of the sent transaction.
    """
    # Validate the recipient address
    if not w3.is_address(recipient_address):
        raise ValueError(f"Invalid recipient address: {recipient_address}")

    # Convert ETH amount to Wei
    amount_wei: int = w3.to_wei(amount_eth, 'ether')

    # Convert gas price to Wei
    gas_price_wei: int = w3.to_wei(gas_price_gwei, 'gwei')

    # Get the transaction nonce
    nonce: int = w3.eth.get_transaction_count(sender_account)

    # Build the transaction
    tx = {
        'to': recipient_address,
        'value': amount_wei,
        'gas': 21000,  # Standard for ETH transfer
        'gasPrice': gas_price_wei,
        'nonce': nonce,
    }

    tx_hash = w3.eth.send_transaction({
        "from": sender_account,
        "to": recipient_address,
        "value": w3.to_wei(amount_eth, 'ether'),
    })

    tx = w3.eth.get_transaction(tx_hash)

    print(f"Transaction sent! Hash: {tx_hash.hex()}")

    return tx.__str__()


def get_eth_balance(address: str) -> str:
    """
    Check the balance of a wallet address on the Ethereum blockchain.

    Args:
        address (str): The wallet address to check the balance of.

    Returns:
        str: The balance in Ether (ETH).
    """

    # Validate the address
    if not w3.is_address(address):
        raise ValueError(f"Invalid Ethereum address: {address}")

    # Get the balance in Wei
    balance_wei = w3.eth.get_balance(Web3.to_checksum_address(address))

    # Convert Wei to Ether
    balance_eth = w3.from_wei(balance_wei, 'ether')

    return str(balance_eth)


def get_token_balance(address: str, token_address: str) -> str:
    """
    Check the balance of a specific ERC-20 token in a wallet address.

    Args:
        address (str): The wallet address to check the token balance of.
        token_address (str): The address of the ERC-20 token.

    Returns:
        str: The token balance.
    """

    # Load the ERC-20 ABI
    erc20_abi = load_abi('./abi/erc20.json')

    # Initialize the contract
    erc20_contract = w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=erc20_abi)

    # Get the balance
    balance = erc20_contract.functions.balanceOf(address).call()

    return str(balance)


def wrap_eth(amount: int):
    """
    Wrap ETH to WETH.

    Args:
        amount (int): Amount of ETH to wrap (in wei).

    Returns:
        str: Transaction hash of the wrap transaction.
    """

    # TODO: chain_id, fix 'weth' identifier
    weth_address = get_crypto_context('1')['addresses']['WETH']

    weth_abi = load_abi('./abi/weth.json')
    weth_contract = w3.eth.contract(address=weth_address, abi=weth_abi)

    tx_hash = weth_contract.functions.deposit().transact(
        {"from": wallet.address, "value": amount})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    return receipt


def swap_tokens(
    token_in: str | None,
    token_out: str | None,
    amount_in: int,
    recipient: str,
    slippage_tolerance: float,
    deadline: int
):
    """
    Swap tokens using the Uniswap Universal Router.

    Args:
        token_in: Address of the token to swap from or None for ETH.
        token_out: Address of the token to swap to or None for ETH.
        amount_in: Amount of `from_token` to swap (in wei).
        recipient: Address to receive the swapped tokens.
        slippage_tolerance: Maximum allowed slippage as a fraction (e.g., 0.01 for 1%).
        deadline: UNIX timestamp for the swap deadline.

    Returns:
        str: Transaction hash of the swap transaction.
    """

    print(f"Swapping {amount_in} {token_in} for {token_out}...")

    # todo: chain_id
    router_address = Web3.to_checksum_address(get_crypto_context(
        '1')['addresses']['uniswap']['universal_router'])

    router_abi = load_abi('./abi/uniswap_swap_router.json')
    router_contract = w3.eth.contract(address=router_address, abi=router_abi)

    erc20_abi = load_abi('./abi/erc20.json')
    erc20_contract = w3.eth.contract(
        address=Web3.to_checksum_address(token_in), abi=erc20_abi)

    allowance = erc20_contract.functions.allowance(
        wallet.address, router_address).call()
    print(f"Allowance: {allowance}")

    # max_allowance = 2**256 - 1
    if allowance < amount_in:
        # Approve the router to spend the input token
        print('Approving token...')
        tx_hash = erc20_contract.functions.approve(
            router_address, amount_in).transact({"from": wallet.address})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        print(f"Approved")

    fee = 3000
    path = Web3.to_bytes(hexstr=Web3.to_checksum_address(token_in)) + fee.to_bytes(
        3, 'big') + Web3.to_bytes(hexstr=Web3.to_checksum_address(token_out))

    # inputs = [encode(['address', 'uint256', 'uint256', 'bytes', 'bool'], [Web3.to_checksum_address(recipient), amount_in, 0, path, True])] # TODO: Minimum output amount

    tx_hash = router_contract.functions.exactInputSingle([Web3.to_checksum_address(token_in), Web3.to_checksum_address(
        token_out), fee, recipient, amount_in, 0, 0]).transact({"from": wallet.address})
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    # print(f"Transaction sent with hash: {receipt}")
    return receipt


def add_v3_liquidity(position_manager_address, token0, token1, fee, amount0_desired, amount1_desired, recipient):
    """
    Adds liquidity to a Uniswap V3 pool.

    Parameters:
        router_address (str): Address of the NonfungiblePositionManager contract.
        token0 (str): Address of the first token in the pool.
        token1 (str): Address of the second token in the pool.
        fee (int): Pool fee (e.g., 3000 for 0.3%).
        amount0_desired (int): Amount of token0 to provide.
        amount1_desired (int): Amount of token1 to provide.
        recipient (str): Address to receive the liquidity position NFT.

    Returns:
        dict: Transaction receipt.
    """
    # Load the NonfungiblePositionManager contract
    # Replace with the ABI of the NonfungiblePositionManager contract
    non_pos_abi = load_abi('non_fungible_position_manager.json')
    router = w3.eth.contract(address=position_manager_address, abi=non_pos_abi)

    # Define parameters for mint function
    params = {
        "token0": Web3.to_checksum_address(token0),
        "token1": Web3.to_checksum_address(token1),
        "fee": fee,
        "tickLower": -887272,  # Replace with appropriate value
        "tickUpper": 887272,   # Replace with appropriate value
        "amount0Desired": amount0_desired,
        "amount1Desired": amount1_desired,
        "amount0Min": 0,       # Adjust as needed to prevent slippage
        "amount1Min": 0,       # Adjust as needed to prevent slippage
        "recipient": Web3.to_checksum_address(recipient),
        # 10-minute deadline
        "deadline": w3.eth.get_block("latest").timestamp + 600,
    }

    # Encode the transaction data
    txn = router.functions.mint(params).build_transaction({
        "from": wallet.address,
        "gas": 3000000,
        "gasPrice": w3.eth.gas_price,
        "nonce": w3.eth.get_transaction_count(wallet.address),
    })

    # Sign the transaction
    signed_txn = w3.eth.account.sign_transaction(txn)

    # Send the transaction
    txn_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

    # Wait for the transaction receipt
    receipt = w3.eth.wait_for_transaction_receipt(txn_hash)

    return receipt


def remove_v3_liquidity(
    universal_router_address: str,
    token_id: int,
    liquidity: int,
    amount0_min: int,
    amount1_min: int,
    recipient: str,
    deadline: int
):
    """
    Remove liquidity from a Uniswap V3 pool.

    Args:
        universal_router_address (str): Address of the Uniswap Universal Router.
        token_id (int): ID of the liquidity position NFT.
        liquidity (int): Amount of liquidity to burn (in wei).
        amount0_min (int): Minimum amount of `token0` to receive.
        amount1_min (int): Minimum amount of `token1` to receive.
        recipient (str): Address to receive the tokens from the liquidity position.
        deadline (int): UNIX timestamp for the transaction deadline.

    Returns:
        str: Transaction hash of the remove liquidity operation.
    """
    account = wallet.account

    router_abi = [...]  # Replace with Universal Router ABI
    universal_router = w3.eth.contract(
        address=universal_router_address, abi=router_abi)

    remove_liquidity_data = universal_router.encodeABI(
        fn_name="removeLiquidityV3",
        args=[
            {
                "tokenId": token_id,
                "liquidity": liquidity,
                "amount0Min": amount0_min,
                "amount1Min": amount1_min,
                "recipient": recipient,
                "deadline": deadline,
            }
        ]
    )

    transaction = {
        "to": universal_router_address,
        "value": 0,
        "gas": 300000,
        "gasPrice": w3.eth.gas_price,
        "nonce": w3.eth.get_transaction_count(account.address),
        "data": remove_liquidity_data,
    }

    signed_txn = account.sign_transaction(transaction)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
    return w3.toHex(tx_hash)


def supply_asset(
    lending_pool_address: str,
    asset: str,
    amount: int,
    on_behalf_of: str = None
):
    """
    Supply an asset to Aave to earn interest.

    Args:
        lending_pool_address (str): Address of the Aave LendingPool contract.
        asset (str): Address of the ERC-20 token to supply.
        amount (int): Amount of the token to supply (in wei).
        on_behalf_of (str): Address on whose behalf the asset is being supplied.

    Returns:
        str: Transaction hash of the supply operation.
    """

    # Default "on_behalf_of" to the caller's wallet address if not provided
    if on_behalf_of is None:
        on_behalf_of = wallet.address

    # Load ABIs
    lending_pool_abi = load_abi('./abi/aave_pool.json')
    erc20_abi = load_abi('./abi/erc20.json')

    # Initialize contracts
    lending_pool = w3.eth.contract(
        address=Web3.to_checksum_address(lending_pool_address), abi=lending_pool_abi)
    token_contract = w3.eth.contract(
        address=Web3.to_checksum_address(asset), abi=erc20_abi)

    # Approve the LendingPool to spend the token
    approve_txn_hash = w3.eth.send_transaction({
        "from": wallet.address,
        "to": asset,
        "data": token_contract.encode_abi("approve", args=[lending_pool_address, amount])
    })
    w3.eth.wait_for_transaction_receipt(approve_txn_hash)

    # Supply the asset
    supply_txn_hash = w3.eth.send_transaction({
        "from": wallet.address,
        "to": lending_pool_address,
        "data": lending_pool.encode_abi("deposit", args=[asset, amount, on_behalf_of, 0])
    })

    return w3.to_hex(supply_txn_hash)


def withdraw_asset(
    lending_pool_address: str,
    asset: str,
    amount: int,
):
    """
    Withdraw a supplied asset from Aave.

    Args:
        lending_pool_address (str): Address of the Aave LendingPool contract.
        asset (str): Address of the ERC-20 token to withdraw.
        amount (int): Amount of the token to withdraw (in wei). Use `2**256 - 1` to withdraw the full balance.

    Returns:
        str: Transaction hash of the withdrawal operation.
    """

    print(f"Withdrawing {amount} {asset} from Aave...")

    # Load the LendingPool ABI
    lending_pool_abi = load_abi('./abi/aave_pool.json')
    lending_pool = w3.eth.contract(
        address=Web3.to_checksum_address(lending_pool_address), abi=lending_pool_abi)

    # Send the withdrawal transaction
    withdraw_txn_hash = w3.eth.send_transaction({
        "from": wallet.address,
        "to": lending_pool_address,
        "data": lending_pool.encode_abi("withdraw", args=[asset, amount, wallet.address])
    })

    return w3.to_hex(withdraw_txn_hash)


def search_tokens(chain_id: str):
    """
    Search for tokens on a specific chain.

    Args:
        chainId (str): The chain ID to search on.

    Returns:
        dict: A dictionary of token addresses and metadata.
    """
    return tokens.get(chain_id, '1')


def get_token_data(chain_id: str, address: str):
    """
    Get token data for whitelisted tokens. Alert if token is not whitelisted.

    Returns:
        dict: A dictionary containing token addresses and metadata.
    """
    return tokens.get(chain_id, '1').get(address, 'Not found.')

# supported_chains = [1, 10, 42, 56, 137, 8453, 42161, 81457]


def get_crypto_context(chain_id: str):
    """
    Fetch global crypto-related variables such as contract addresses for uniswap and aave, 
    slippage settings, and other key parameters for on-chain operations.

    Returns:
        dict: A dictionary containing contract addresses, slippage settings, gas limits, etc.
    """
    addresses = {
        "1": {
            "WETH": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
            "uniswap": {
                "position_manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
                "universal_router": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
                "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
            },
            "aave": {
                "pool": "0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2",
            }
        },
        "10": {
            "WETH": "0x4200000000000000000000000000000000000006",
            "uniswap": {
                "position_manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
                "universal_router": "0xCb1355ff08Ab38bBCE60111F1bb2B784bE25D7e8",
                "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
            },
            "aave": {
                "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
            }
        },
        "56": {
            "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
            "uniswap": {
                "position_manager": "0x7b8A01B39D58278b5DE7e48c8449c9f4F5170613",
                "universal_router": "0x4Dae2f939ACf50408e13d58534Ff8c2776d45265",
                "factory": "0xdB1d10011AD0Ff90774D0C6Bb92e5C5c8b4461F7",
            },
            "aave": {
                "pool": "0x6807dc923806fE8Fd134338EABCA509979a7e0cB",
            }
        },
        "137": {
            "WMATIC": "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",
            "uniswap": {
                "position_manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
                "universal_router": "0xec7BE89e9d109e7e3Fec59c222CF297125FEFda2",
                "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
            },
            "aave": {
                "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
            }
        },
        "8453": {
            "WETH": "0x4200000000000000000000000000000000000006",
            "uniswap": {
                "position_manager": "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1",
                "universal_router": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
                "factory": "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
            },
            "aave": {
                "pool": "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5",
            }
        },
        "42161": {
            "WETH": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
            "uniswap": {
                "position_manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
                "universal_router": "0x5E325eDA8064b456f4781070C0738d849c824258",
                "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
            },
            "aave": {
                "pool": "0x794a61358D6845594F94dc1DB02A252b5b4814aD",
            }
        },
    }

    return {
        "addresses": addresses[chain_id],
        "slippage": "0.5",  # in percentage
        "gas_limit": "300000",  # default gas limit
    }


# Create the Based Agent with all available functions
based_agent = Agent(
    name="Based Agent",
    model="gpt-4o-mini",
    instructions=f"You are a helpful agent we are debugging on forked Ethereum so don't worry about mistakes or errors. We are learning. You can send ETH, swap tokens, add & remove liquidty for a liquidity pool, and add & remove assets for lending in AAVE. If you ever need to know your address, it is {wallet.address}. If you can't find an address or setting there, ask.",
    functions=[
        get_eth_balance,
        get_token_balance,
        send_eth,
        add_v3_liquidity,
        remove_v3_liquidity,
        supply_asset,
        withdraw_asset,
        swap_tokens,
        search_tokens,
        get_crypto_context,
        get_token_data,
        wrap_eth
    ],
)

# To add a new function:
# 1. Define your function above (follow the existing pattern)
# 2. Add appropriate error handling
# 3. Add the function to the based_agent's functions list
# 4. If your function requires new imports or global variables, add them at the top of the file
# 5. Test your new function thoroughly before deploying

# Example of adding a new function:
# def my_new_function(param1, param2):
#     """
#     Description of what this function does.
#
#     Args:
#         param1 (type): Description of param1
#         param2 (type): Description of param2
#
#     Returns:
#         type: Description of what is returned
#     """
#     try:
#         # Your function logic here
#         result = do_something(param1, param2)
#         return f"Operation successful: {result}"
#     except Exception as e:
#         return f"Error in my_new_function: {str(e)}"

# Then add to based_agent.functions:
# based_agent = Agent(
#     ...
#     functions=[
#         ...
#         my_new_function,
#     ],
# )
