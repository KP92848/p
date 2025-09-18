import requests
import pandas as pd
from datetime import datetime

BASE_URL = "http://localhost:8000/lookthrough/v1"

def get_value_by_country_or_region(date: str, fund_ids: str, kwargs: dict) -> pd.DataFrame:
    """
    Simplified adapter function to route old PyMAF calls to new Hyperion API.
    Returns the same DataFrame format as the original Hyperion function.
    """
    
    # Parse inputs
    quasar_codes = fund_ids.strip("'").replace("','", ";").split(";")
    formatted_date = datetime.strptime(date, '%d/%m/%Y' if '/' in date else '%Y-%m-%d').strftime("%Y-%m-%d")
    
    # Build query options - only include what's provided
    query_options = {}
    
    if "value" in kwargs:
        query_options["value"] = kwargs["value"]
    if "group" in kwargs:
        query_options["group"] = kwargs["group"]
    if "asset_type" in kwargs:
        query_options["asset_type"] = kwargs["asset_type"]
    if "top" in kwargs:
        query_options["top"] = kwargs["top"]
    
    # Handle splits
    splits = {}
    if kwargs.get("split_countries"):
        splits["countries"] = str(kwargs["split_countries"]).split(";")
    if kwargs.get("split_regions"):
        splits["regions"] = str(kwargs["split_regions"]).split(";")
    if kwargs.get("split_em") == 1:
        splits.setdefault("regions", []).append("EM")
    if kwargs.get("split_middle_east") == 1:
        splits.setdefault("regions", []).append("Middle East")
    
    if splits:
        query_options["splits"] = splits
    
    # Make API call
    response = requests.post(
        f"{BASE_URL}/value_by_country_or_region",
        headers={"Content-Type": "application/json"},
        json={
            "valuation_date": formatted_date,
            "quasar_codes": quasar_codes,
            "query_options": query_options
        }
    )
    
    if response.status_code == 200:
        response_data = response.json()
        return unpack_response_to_dataframe(response_data)
    else:
        raise Exception(f"API call failed: {response.status_code} - {response.text}")

def unpack_response_to_dataframe(response_data) -> pd.DataFrame:
    """
    Unpack the nested API response into a flat DataFrame.
    
    Expected response format:
    {
        "request_id": "...",
        "duration": 6.84,
        "funds": {
            "fund_id": "2820",
            "axis": "region", 
            "values": [
                {"key": "North America", "value": 34.68, "type": "PERCENT", "label": "weight_by_region"},
                ...
            ]
        }
    }
    """
    rows = []
    
    # Handle single fund response or list of funds
    if isinstance(response_data.get("funds"), dict):
        funds_data = [response_data["funds"]]
    else:
        funds_data = response_data.get("funds", [])
    
    for fund_data in funds_data:
        fund_id = fund_data.get("fund_id")
        axis = fund_data.get("axis")
        
        for value_item in fund_data.get("values", []):
            row = {
                "fund_id": fund_id,
                "axis": axis,
                "key": value_item.get("key"),
                "value": value_item.get("value"),
                "type": value_item.get("type"),
                "label": value_item.get("label")
            }
            rows.append(row)
    
    return pd.DataFrame(rows)


# Test function
def test_adapter():
    """Test the adapter with sample data"""
    
    # Sample kwargs that might come from PyMAF
    test_kwargs = {
        "value": "POSITION_VALUE",
        "group": "REGION", 
        "split_em": 1,
        "split_middle_east": 1
    }
    
    try:
        result = get_value_by_country_or_region(
            date="2024-01-01",
            fund_ids="'2820'",
            kwargs=test_kwargs
        )
        print("Success! DataFrame shape:", result.shape)
        print("\nColumns:", result.columns.tolist())
        print("\nFirst few rows:")
        print(result.head())
        return result
        
    except Exception as e:
        print(f"Test failed: {e}")
        return None


if __name__ == "__main__":
    test_adapter()