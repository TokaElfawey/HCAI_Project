from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
class GeminiLLM:
    def __init__(self, api_key, model="gemini-3.5-flash-lite", temperature=0.3):
        from google import genai
        from google.genai import types
        self.types = types
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.temperature = temperature
    # ==========================================
    # Convert message content into text
    # ==========================================
    @staticmethod
    def get_text(content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(block.get("text", "") if isinstance(block, dict) else str(block) for block in content)
        return str(content)
    # ==========================================
    # Main LLM function
    # ==========================================
    def invoke(self, messages):
        system_instruction = ""
        contents = []
        # Convert LangChain messages into Gemini messages
        for message in messages:
            text = self.get_text(message.content)
            # Extract system prompt
            if isinstance(message, SystemMessage):
                system_instruction = text
                continue
            # Convert HumanMessage to user
            elif isinstance(message, HumanMessage):
                role = "user"
            # Convert AIMessage to model
            elif isinstance(message, AIMessage):
                role = "model"
            else:
                continue
            if not text.strip():
                continue
            part = self.types.Part.from_text(text=text)
            # Merge consecutive messages with the same role
            if contents and contents[-1].role == role:
                contents[-1] = self.types.Content(role=role, parts=contents[-1].parts + [part])
            else:
                contents.append(self.types.Content(role=role, parts=[part]))
        # Gemini conversation should start with a user message
        while contents and contents[0].role != "user":
            contents.pop(0)
        if not contents:
            raise ValueError("No user messages provided to Gemini.")
        # Send request to Gemini API
        response = self.client.models.generate_content(model=self.model, contents=contents, config=self.types.GenerateContentConfig(system_instruction=system_instruction or None, temperature=self.temperature))
        # Extract Gemini response
        reply = response.text
        if not reply:
            raise RuntimeError("Gemini returned an empty response.")
        # Return LangChain-compatible response
        return AIMessage(content=reply)
