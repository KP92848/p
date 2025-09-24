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


def get_portfolio_value_by_classification(date: str, fund_ids: str, kwargs: dict) -> pd.DataFrame:
    """
    Get portfolio values by classification (region_em, bics_l1, etc.)
    Returns DataFrame with proper multi-level index and clean column separation.
    """
    
    # Parse inputs
    quasar_codes = fund_ids.strip("'").replace("','", ";").split(";")
    formatted_date = datetime.strptime(date, '%d/%m/%Y' if '/' in date else '%Y-%m-%d').strftime("%Y-%m-%d")
    
    # Build query options - include classification-specific parameters
    query_options = {}
    
    if "value" in kwargs:
        query_options["value"] = kwargs["value"]
    if "group" in kwargs:
        query_options["group"] = kwargs["group"]
    if "asset_type" in kwargs:
        query_options["asset_type"] = kwargs["asset_type"]
    if "top" in kwargs:
        query_options["top"] = kwargs["top"]
    
    # Handle classification splits - this is key for proper output format
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
    
    # Make API call to classification endpoint
    response = requests.post(
        f"{BASE_URL}/value_by_classification",
        headers={"Content-Type": "application/json"},
        json={
            "valuation_date": formatted_date,
            "quasar_codes": quasar_codes,
            "query_options": query_options
        }
    )
    
    if response.status_code == 200:
        response_data = response.json()
        return unpack_classification_response_to_dataframe(response_data)
    else:
        raise Exception(f"API call failed: {response.status_code} - {response.text}")


def unpack_classification_response_to_dataframe(response_data) -> pd.DataFrame:
    """
    Unpack the nested classification API response into properly formatted DataFrame.
    
    Expected response format for classification:
    {
        "request_id": "...",
        "duration": 6.84,
        "funds": [
            {
                "fund_id": "9005",
                "axis": "classification", 
                "values": [
                    {
                        "key": {"region_em": "Asia Pacific Ex Japan", "bics_l1": "Communications"},
                        "value": 0.04567,
                        "type": "PERCENT",
                        "label": "weight_by_classification"
                    },
                    ...
                ]
            }
        ]
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
        
        for value_item in fund_data.get("values", []):
            # Extract classification keys properly
            key_data = value_item.get("key", {})
            
            # Handle different key formats
            if isinstance(key_data, dict):
                region_em = key_data.get("region_em", "Unclassifiable")
                bics_l1 = key_data.get("bics_l1", "Unclassifiable")
            elif isinstance(key_data, str):
                # If key is a string, try to parse it
                if "," in key_data:
                    parts = key_data.split(",")
                    region_em = parts[0].strip() if len(parts) > 0 else "Unclassifiable"
                    bics_l1 = parts[1].strip() if len(parts) > 1 else "Unclassifiable"
                else:
                    region_em = key_data
                    bics_l1 = "Unclassifiable"
            else:
                region_em = "Unclassifiable"
                bics_l1 = "Unclassifiable"
            
            row = {
                "fund_id": fund_id,
                "region_em": region_em,
                "bics_l1": bics_l1,
                "value": value_item.get("value", 0.0)
            }
            rows.append(row)
    
    if not rows:
        # Return empty DataFrame with proper structure
        return pd.DataFrame(columns=["fund_id", "region_em", "bics_l1", "value"])
    
    df = pd.DataFrame(rows)
    
    # Create pivot table with proper multi-level index
    pivot_df = df.pivot_table(
        index=["region_em", "bics_l1"],
        columns="fund_id",
        values="value",
        aggfunc="sum",
        fill_value=0.0
    )
    
    # Clean up column names and ensure proper formatting
    pivot_df.columns.name = None
    
    # Ensure numeric values are properly formatted
    pivot_df = pivot_df.round(5)
    
    return pivot_df


# Test functions
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


def test_classification_adapter():
    """Test the classification adapter with sample data"""
    
    # Sample kwargs for classification
    test_kwargs = {
        "value": "POSITION_VALUE",
        "group": "CLASSIFICATION", 
        "split_em": 1
    }
    
    try:
        result = get_portfolio_value_by_classification(
            date="2024-01-01",
            fund_ids="'9005','Portfolio'",
            kwargs=test_kwargs
        )
        print("Classification Success! DataFrame shape:", result.shape)
        print("\nColumns:", result.columns.tolist())
        print("\nIndex levels:", result.index.names)
        print("\nFirst few rows:")
        print(result.head())
        return result
        
    except Exception as e:
        print(f"Classification test failed: {e}")
        return None


def test_classification_with_mock_data():
    """Test classification function with mock response data"""
    
    # Mock response data that simulates what the API would return
    mock_response = {
        "request_id": "test-123",
        "duration": 1.2,
        "funds": [
            {
                "fund_id": "9005",
                "axis": "classification",
                "values": [
                    {
                        "key": {"region_em": "Asia Pacific Ex Japan", "bics_l1": "Communications"},
                        "value": 0.04567,
                        "type": "PERCENT",
                        "label": "weight_by_classification"
                    },
                    {
                        "key": {"region_em": "Asia Pacific Ex Japan", "bics_l1": "Technology"},
                        "value": 0.03245,
                        "type": "PERCENT",
                        "label": "weight_by_classification"
                    }
                ]
            },
            {
                "fund_id": "Portfolio",
                "axis": "classification",
                "values": [
                    {
                        "key": {"region_em": "Asia Pacific Ex Japan", "bics_l1": "Communications"},
                        "value": 0.04449,
                        "type": "PERCENT",
                        "label": "weight_by_classification"
                    },
                    {
                        "key": {"region_em": "Asia Pacific Ex Japan", "bics_l1": "Technology"},
                        "value": 0.03122,
                        "type": "PERCENT",
                        "label": "weight_by_classification"
                    }
                ]
            }
        ]
    }
    
    try:
        result = unpack_classification_response_to_dataframe(mock_response)
        print("Mock data test successful!")
        print(f"DataFrame shape: {result.shape}")
        print(f"Index names: {result.index.names}")
        print(f"Column names: {result.columns.tolist()}")
        print("\nResult:")
        print(result)
        return result
        
    except Exception as e:
        print(f"Mock data test failed: {e}")
        return None


def test_classification_with_edge_cases():
    """Test classification function with edge cases including Unclassifiable entries"""
    
    # Mock response data with edge cases
    mock_response = {
        "request_id": "test-edge-123",
        "duration": 1.2,
        "funds": [
            {
                "fund_id": "9005",
                "axis": "classification",
                "values": [
                    {
                        "key": {"region_em": "Asia Pacific Ex Japan", "bics_l1": "Communications"},
                        "value": 0.04567,
                        "type": "PERCENT",
                        "label": "weight_by_classification"
                    },
                    {
                        "key": {"region_em": "Unclassifiable", "bics_l1": "Unclassifiable"},
                        "value": 0.01234,
                        "type": "PERCENT",
                        "label": "weight_by_classification"
                    },
                    {
                        "key": "North America,Energy",  # String format test
                        "value": 0.02345,
                        "type": "PERCENT",
                        "label": "weight_by_classification"
                    },
                    {
                        "key": {},  # Empty key test
                        "value": 0.00567,
                        "type": "PERCENT",
                        "label": "weight_by_classification"
                    }
                ]
            },
            {
                "fund_id": "Portfolio", 
                "axis": "classification",
                "values": [
                    {
                        "key": {"region_em": "Asia Pacific Ex Japan", "bics_l1": "Communications"},
                        "value": 0.04449,
                        "type": "PERCENT",
                        "label": "weight_by_classification"
                    },
                    {
                        "key": {"region_em": "Unclassifiable", "bics_l1": "Unclassifiable"},
                        "value": 0.01111,
                        "type": "PERCENT",
                        "label": "weight_by_classification"
                    },
                    {
                        "key": "North America,Energy",
                        "value": 0.02222,
                        "type": "PERCENT",
                        "label": "weight_by_classification"
                    },
                    {
                        "key": {},
                        "value": 0.00444,
                        "type": "PERCENT",
                        "label": "weight_by_classification"
                    }
                ]
            }
        ]
    }
    
    try:
        result = unpack_classification_response_to_dataframe(mock_response)
        print("Edge cases test successful!")
        print(f"DataFrame shape: {result.shape}")
        print(f"Index names: {result.index.names}")
        print(f"Column names: {result.columns.tolist()}")
        print("\nResult:")
        print(result)
        
        # Test that problematic tuple formatting doesn't occur
        index_str_representation = str(result.index)
        if "(" in index_str_representation and ")" in index_str_representation:
            print("\n⚠️  Warning: Index might contain tuples")
        else:
            print("\n✅ Index formatting looks correct - no tuples detected")
            
        return result
        
    except Exception as e:
        print(f"Edge cases test failed: {e}")
        return None


if __name__ == "__main__":
    print("Testing original adapter...")
    test_adapter()
    
    print("\n" + "="*50)
    print("Testing classification adapter with mock data...")
    test_classification_with_mock_data()
    
    print("\n" + "="*50)
    print("Testing classification adapter with edge cases...")
    test_classification_with_edge_cases()
    
    print("\n" + "="*50)
    print("Testing classification adapter with API call...")
    test_classification_adapter()