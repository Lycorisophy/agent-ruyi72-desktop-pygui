---
name: stockapi
description: Skill for interacting with StockAPI, including finding interfaces and generating Python code.
---

Here are the instructions for the `stockapi` skill.

## Description

This skill assists users in finding the correct StockAPI interface based on their natural language description, explaining the data fields, generating, and automatically executing Python code to call the interface. It leverages the `api_docs.md` file in the same directory for API definitions.

## Workflow

1.  **Analyze User Request**: Understand what data or functionality the user is looking for (e.g., "A股列表", "K线行情", "MACD指标").
2.  **Find Matching API**:
    - Search the `api_docs.md` file in the skill directory for relevant keywords using `grep` or `read`.
    - Identify the most appropriate API based on the description and return fields.
3.  **Explain & Confirm**:
    - Present the found API (Name, ID, URL, Description) to the user.
    - Explain the input parameters and return fields.
    - Ask the user to confirm if this is the correct interface.
4.  **Gather Parameters**:
    - If the user confirms, ask for any necessary parameters (e.g., stock code, date range) if not already provided.
    - If the user has questions about parameters, explain them using the API documentation.
5.  **Generate Code**:
    - **Request Construction Strategy**:
      - Locate the line starting with `**有Token示例**:` in the `api_docs.md` for the chosen API (e.g., `https://www.stockapi.com.cn/v1/base/jjqc?tradeDate=2025-03-04&period=0&type=1&token=你的token`).
      - Extract the base URL and the query parameters from this example URL.
      - Refer to the "请求参数" (Request Parameters) table immediately following the example to understand the meaning, type, and required status of each parameter.
      - Construct the `requests.get` call using a `params` dictionary that includes `token` and all other necessary parameters found in the example and table.
    - Write Python code using the `requests` library to call the API.
    - Include error handling (check if `code == 20000`).
    - **Automatic Token Reading**:
      - The generated code MUST attempt to read the `Token` from `api_docs.md` automatically.
      - Use `os.path` to locate `api_docs.md` relative to the script's location (e.g., inside `.trae/skills/stockapi/`).
      - If the token is found in the file, use it directly without prompting the user.
      - **Only** if the token is NOT found or cannot be read, prompt the user to input it using `input("请先输入你的stockapi专属token: ")`.

6.  **Run Code**:
    - After the code is generated and saved, use the `RunCommand` tool to execute the python script (e.g., `python <filename>`).
    - Set `blocking: true` for the command.
    - Inform the user that the code is running.

## Code Template

```python
import requests
import os

# Global variable for token
TOKEN = ""

def get_token_from_file():
    global TOKEN
    try:
        # Locate api_docs.md relative to the script or project root
        # Adjust path logic as needed based on where the script is saved
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Example path: .trae/skills/stockapi/api_docs.md
        # You might need to traverse up or down depending on script location
        docs_path = os.path.join(current_dir, ".trae", "skills", "stockapi", "api_docs.md")

        if os.path.exists(docs_path):
            with open(docs_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip().startswith("Token="):
                        TOKEN = line.strip().split("=")[1].strip()
                        print(f"Token found in api_docs.md: {TOKEN[:5]}...")
                        return TOKEN
    except Exception as e:
        print(f"Error reading token file: {e}")
    return ""

def call_stock_api(token, ...):
    url = "https://www.stockapi.com.cn/v1/..."  # Replace with actual URL
    params = {
        "token": token,
        # Add other parameters here
    }
    try:
        response = requests.get(url, params=params)
        data = response.json()
        if data.get("code") == 20000:
            print("Success:", data.get("data"))
            return data.get("data")
        else:
            print("Error:", data.get("msg"))
            return None
    except Exception as e:
        print(f"Request failed: {e}")
        return None

if __name__ == "__main__":
    # 1. Try to read token from file
    get_token_from_file()

    # 2. If not found, prompt user
    if not TOKEN:
        TOKEN = input("请先输入你的stockapi专属token: ")
    else:
        print("Using token from api_docs.md")

    # Call the function with the token
    call_stock_api(TOKEN, ...)
```

## Knowledge Source

The full API documentation is located at `api_docs.md` in this directory. Always refer to this file for the most accurate and up-to-date information on API endpoints, parameters, and response structures.
