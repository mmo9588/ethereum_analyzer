import streamlit as st
import pandas as pd
from ethereum_utils import scrape_multiple_wallets
import requests

st.set_page_config(layout="wide")

def check_proxy(proxy_str):
    if not proxy_str:
        return False
    
    proxy = {
        "http": f"http://{proxy_str}",
        "https": f"http://{proxy_str}",
    }
    url = "http://ip-api.com/json/" 
    try:
        response = requests.get(url, proxies=proxy, timeout=10)
        response.raise_for_status()
        data = response.json()
        st.success(f"Proxy Verified! Request IP: {data['query']} (Location: {data['country']})")
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Proxy Check Failed: {e}")
        return False

def main():
    st.title("Blockchain Wallet Analysis Tool")
    
    st.markdown("""
    ### Instructions:
    1. (Optional) Enter a proxy 
    2. Select blockchain network (Ethereum)
    3. Enter wallet addresses (one per line)
    4. Specify number of transactions to analyze
    5. Click 'Start Analysis' to begin
    """)
    
    # Proxy Input
    proxy_input = st.text_input(
        "Enter Proxy (Optional - format: ip:port)", 
        placeholder="e.g., 123.45.67.89:8080",
        help="Leave blank if not using a proxy"
    )
    
    # Proxy Verification Button
    if st.button("Verify Proxy"):
        proxy_verified = check_proxy(proxy_input)
        if not proxy_verified:
            st.warning("Please enter a valid proxy or leave blank.")
            return
    
    network = st.selectbox(
        "Select Blockchain Network",
        ["Ethereum"]
    )
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        wallet_addresses = st.text_area(
            "Enter wallet addresses (one per line):",
            height=200,
            help="Enter each wallet address on a new line"
        )
    
    with col2:
        max_transactions = st.number_input(
            "Transactions to analyze per wallet",
            min_value=1,
            max_value=10000,
            value=100
        )
    
    if st.button("Start Analysis"):
        if not wallet_addresses.strip():
            st.error("Please enter wallet addresses before starting the analysis.")
            return
            
        addresses = [addr.strip() for addr in wallet_addresses.split('\n') if addr.strip()]
        
        if len(addresses) == 0:
            st.error("Please enter at least one valid wallet address.")
            return
            
        st.info(f"Starting analysis for {len(addresses)} wallet addresses, analyzing {max_transactions} transactions per wallet...")
        
        if network == "Ethereum":
            process_ethereum(addresses, max_transactions, proxy_input)

def process_ethereum(addresses, max_transactions, proxy=None):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    with st.spinner("Analyzing Ethereum wallets..."):
        # Pass proxy to scrape_multiple_wallets function
        transactions, common_addresses = scrape_multiple_wallets(
            addresses, 
            max_transactions, 
            progress_bar, 
            status_text,
            proxy  # Pass proxy information
        )
        
        if transactions:
            progress_bar.progress(1.0)
            status_text.text("Analysis complete!")
            st.success("Analysis complete!")
            
            display_data = []
            for addr, wallets in common_addresses.items():
                display_data.append({
                    "From Address": addr,
                    "Number of Connected Wallets": len(wallets),
                    "Connected Wallets": ", ".join(wallets)
                })
            
            df = pd.DataFrame(display_data)
            csv = df.to_csv(index=False)
            
            st.download_button(
                label="Download results as CSV",
                data=csv,
                file_name="ethereum_analysis.csv",
                mime="text/csv"
            )
            
            st.subheader("Analysis Results")
            for addr, wallets in common_addresses.items():
                with st.expander(f"From Address: {addr} (Connected to {len(wallets)} wallets)"):
                    col1, col2 = st.columns([4, 1])
                    
                    with col1:
                        st.write("Connected to the following wallets:")
                        for idx, wallet in enumerate(wallets, 1):
                            st.code(f"Wallet {idx}: {wallet}")
                    with col2:
                        etherscan_url = f"https://app.zerion.io/{addr}"
                        st.markdown(f'''
                            <a href="{etherscan_url}" target="_blank">
                                <button style="
                                    background-color: #4CAF50;
                                    border: none;
                                    color: white;
                                    padding: 10px 20px;
                                    text-align: center;
                                    text-decoration: none;
                                    display: inline-block;
                                    font-size: 14px;
                                    margin: 4px 2px;
                                    cursor: pointer;
                                    border-radius: 4px;">
                                    Open in Zerion
                                </button>
                            </a>
                            ''', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
