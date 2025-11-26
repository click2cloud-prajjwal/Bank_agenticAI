# agents/base_agent.py
from abc import ABC, abstractmethod
from openai import AzureOpenAI
import os
import json

class BaseAgent(ABC):
    """Base class for all specialized agents"""
    
    def __init__(self, name: str, role: str, instructions: str):
        self.name = name
        self.role = role
        self.instructions = instructions
        self.client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
    
    def call_llm(self, messages: list, temperature: float = 0.7, tools: list = None) -> dict:
        """Call Azure OpenAI with messages"""
        try:
            params = {
                "model": os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 2000
            }
            
            if tools:
                params["tools"] = tools
                params["tool_choice"] = "auto"
            
            response = self.client.chat.completions.create(**params)
            
            # Handle tool calls
            message = response.choices[0].message
            
            if message.tool_calls:
                return {
                    "type": "tool_calls",
                    "tool_calls": message.tool_calls,
                    "message": message
                }
            else:
                return {
                    "type": "text",
                    "content": message.content
                }
        except Exception as e:
            print(f"⚠️ {self.name} LLM Error: {e}")
            return {
                "type": "error",
                "content": f"Error in {self.name}: {str(e)}"
            }
    
    @abstractmethod
    def process(self, context: dict, query: str, conversation_history: list = None) -> dict:
        """Process the query with agent-specific logic and conversation history"""
        pass
    
    def format_response(self, content: str, metadata: dict = None) -> dict:
        """Format agent response"""
        return {
            "agent": self.name,
            "role": self.role,
            "content": content,
            "metadata": metadata or {}
        }