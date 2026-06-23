import os
from dotenv import load_dotenv
from src.llm import LLMProviderFactory

load_dotenv()
api_key = os.getenv("LLM_API_KEY")
model_name = os.getenv("LLM_MODEL")

print(f"API Key (truncated): {api_key[:10]}...{api_key[-5:] if api_key else 'None'}")
print(f"Model Name from env: {model_name}")

try:
    provider = LLMProviderFactory.get_provider()
    print("Resolved Provider Model Name:", provider.model_name)
    
    # 測試一般生成
    print("\nAttempting plain text generation:")
    response = provider.generate("Say hello")
    print("Success! Response:", response)

    # 測試 JSON 生成
    print("\nAttempting JSON generation:")
    json_response = provider.generate_json(
        prompt="Respond with a JSON object containing a field 'status' with value 'ok'",
        system_instruction="Always output JSON"
    )
    print("Success! JSON Response:", json_response)
    
except Exception as e:
    print("Error details:", e)
