# utils/chat_assistant.py
import streamlit as st
import google.generativeai as genai
from typing import Optional, Dict, Any, List
import json

class ChatAssistant:
    """
    AI Chat Assistant powered by Google Gemini API
    Free tier: 60 requests per minute, great for code analysis
    """
    
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        """
        Initialize Gemini chat assistant
        
        Args:
            api_key: Google Gemini API key (free from https://aistudio.google.com/apikey)
            model_name: Gemini model to use
        """
        genai.configure(api_key=api_key)
        
        # Available free models (try in order):
        # "gemini-1.5-flash" - might not work via API
        # "gemini-1.5-flash-latest" - latest flash model
        # "gemini-1.5-pro-latest" - more capable
        # "gemini-pro" - older but stable
        # "gemini-2.0-flash-exp" - experimental
        
        # Try to use the model, fallback if not available
        try:
            self.model = genai.GenerativeModel(model_name)
        except:
            # Fallback to a known working model
            self.model = genai.GenerativeModel("gemini-2.5-flash-latest")
        
        self.repo_context = {}
        self.chat = None
        
        # Generation config for code-focused responses
        self.generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
        }
        
    def set_repo_context(self, context: Dict[str, Any]):
        """Feed repository context to the chatbot"""
        self.repo_context = context
        
        # Safely format all values as strings
        name = str(context.get('name', 'Unknown'))
        primary_lang = str(context.get('primary_language', 'Not detected'))
        total_files = str(context.get('total_files', 0))
        total_lines = str(context.get('total_lines', 0))
        project_type = str(context.get('project_type', 'Unknown'))
        has_tests = str(context.get('has_tests', False))
        has_docker = str(context.get('has_docker', False))
        
        # Format languages - try multiple approaches
        try:
            languages_str = json.dumps(context.get('languages', {}), indent=2)
        except:
            languages_str = str(context.get('languages', 'Not detected'))
        
        # Format tech stack
        tech_stack = context.get('tech_stack', [])
        if isinstance(tech_stack, list):
            tech_stack_str = ', '.join(str(item) for item in tech_stack)
        else:
            tech_stack_str = str(tech_stack)
        
        # Format key files
        key_files = context.get('key_files', [])
        if isinstance(key_files, list):
            key_files_str = ', '.join(str(item) for item in key_files[:10])
        else:
            key_files_str = str(key_files)
        
        # Build simple system context (avoiding JSON entirely)
        system_context = f"""You are SwiftScan AI, an expert code assistant.

Repository: {name}
Primary Language: {primary_lang}
Languages: {languages_str}
Total Files: {total_files}
Total Lines: {total_lines}
Tech Stack: {tech_stack_str}
Key Files: {key_files_str}
Project Type: {project_type}
Has Tests: {has_tests}
Has Docker: {has_docker}

Your role:
1. Explain code architecture in simple terms
2. Help understand project structure
3. Answer technical questions about the codebase
4. Guide setup and troubleshooting

Keep responses concise but helpful."""
        
        # Start chat session
        self.chat = self.model.start_chat(
            history=[
                {"role": "user", "parts": [system_context]},
                {"role": "model", "parts": ["I've analyzed this repository. What would you like to know?"]}
            ]
        )
        
    def generate_response(self, user_message: str) -> str:
        """
        Generate AI response using Gemini
        
        Args:
            user_message: User's question about the repo
            
        Returns:
            AI generated response string
        """
        if not self.chat:
            return "⚠️ Please analyze a repository first before asking questions!"
            
        try:
            response = self.chat.send_message(
                user_message,
                generation_config=self.generation_config
            )
            return response.text
            
        except Exception as e:
            error_msg = str(e)
            if "API_KEY_INVALID" in error_msg:
                return "🔑 Invalid API key. Please check your Gemini API key."
            elif "RATE_LIMIT" in error_msg:
                return "⏳ Rate limit reached. Please wait a moment before asking again."
            elif "SAFETY" in error_msg:
                return "⚠️ Response blocked by safety filters. Please rephrase your question."
            else:
                return f"❌ Error: {error_msg}"

def create_chat_ui(chat_assistant: ChatAssistant):
    """
    Create a chat widget interface in the sidebar
    """
    
    # Initialize session state for chat
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "chat_open" not in st.session_state:
        st.session_state.chat_open = False
    if "chat_processing" not in st.session_state:
        st.session_state.chat_processing = False
    
    # Everything in sidebar
    with st.sidebar:
        st.markdown("---")
        
        # Toggle button
        if st.button(
            "💬 Open Chat Assistant" if not st.session_state.chat_open else "✕ Close Chat Assistant",
            key="chat_toggle_btn",
            use_container_width=True,
            type="primary" if not st.session_state.chat_open else "secondary"
        ):
            st.session_state.chat_open = not st.session_state.chat_open
            st.rerun()
        
        # Show chat interface when toggled on
        if st.session_state.chat_open:
            # Chat header
            st.markdown("""
            <div style='display: flex; align-items: center; gap: 10px; margin: 15px 0;'>
                <span style='font-size: 24px;'>🤖</span>
                <div>
                    <h4 style='margin: 0; color: #00B4C8;'>SwiftScan AI</h4>
                    <small style='color: #64748B;'>Powered by Gemini</small>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Welcome message if no messages yet
            if not st.session_state.chat_messages:
                st.info("""
                👋 **Welcome!** I'm your AI code assistant.
                
                I can help you:
                - 📖 Understand code structure
                - 🔍 Find specific files/functions
                - 💡 Explain complex code
                - 🚀 Setup & configuration help
                
                **What would you like to know?**
                """)
            
            # Display chat messages
            chat_container = st.container(height=350)
            with chat_container:
                for msg in st.session_state.chat_messages:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])
            
            # Chat input
            if user_input := st.chat_input(
                "Ask about this repository...",
                key="gemini_chat_input",
                disabled=st.session_state.chat_processing
            ):
                # Add user message
                st.session_state.chat_messages.append({
                    "role": "user",
                    "content": user_input
                })
                
                # Set processing state
                st.session_state.chat_processing = True
                
                # Generate and add assistant response
                with st.spinner("🤔 Analyzing..."):
                    response = chat_assistant.generate_response(user_input)
                
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": response
                })
                
                st.session_state.chat_processing = False
                st.rerun()
            
            # Clear button
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.chat_messages = []
                st.rerun()

def get_repo_context_for_chat(repo_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract relevant context from repo analysis for the chatbot
    
    Args:
        repo_data: Repository analysis data from SwiftScan
        
    Returns:
        Dictionary with structured repo context
    """
    context = {
        "name": repo_data.get("repo_name", "Unknown"),
        "primary_language": repo_data.get("primary_language", "Not detected"),
        "languages": repo_data.get("languages", {}),
        "total_files": repo_data.get("total_files", 0),
        "total_lines": repo_data.get("total_lines", 0),
        "tech_stack": repo_data.get("tech_stack", []),
        "project_type": repo_data.get("project_type", "General"),
        "key_files": repo_data.get("key_files", []),
        "dependencies": repo_data.get("dependencies", {}),
        "has_tests": repo_data.get("has_tests", False),
        "has_docker": repo_data.get("has_docker", False),
        "has_docs": repo_data.get("has_docs", False),
    }
    
    return context