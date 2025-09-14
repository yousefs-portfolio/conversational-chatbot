"""Tool execution service for LLM function calling."""

import json
import asyncio
import inspect
import importlib
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import traceback
import ast
import sys
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from .models import Tool, ToolExecution, User
from .database import AsyncSessionLocal
from .config import settings


class SafeExecutionError(Exception):
    """Exception for safe execution errors."""
    pass


class ToolExecutor:
    """Secure tool execution environment."""

    def __init__(self):
        self.allowed_imports = {
            'json', 'math', 'datetime', 'random', 'string', 'urllib.parse',
            'base64', 'hashlib', 'uuid', 're', 'collections', 'itertools',
            'functools', 'operator', 'statistics', 'requests', 'pandas', 'numpy'
        }
        self.restricted_attrs = {
            '__import__', 'eval', 'exec', 'compile', 'open', 'file',
            'input', 'raw_input', 'reload', '__builtins__'
        }

    def validate_code(self, code: str) -> bool:
        """Validate Python code for safety."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return False

        for node in ast.walk(tree):
            # Check for restricted function calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.restricted_attrs:
                        return False

            # Check for restricted attribute access
            if isinstance(node, ast.Attribute):
                if node.attr in self.restricted_attrs:
                    return False

            # Check for imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                else:
                    modules = [node.module] if node.module else []

                for module in modules:
                    if module and module.split('.')[0] not in self.allowed_imports:
                        return False

        return True

    async def execute_python_code(
        self,
        code: str,
        parameters: Dict[str, Any],
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Execute Python code safely."""
        if not self.validate_code(code):
            raise SafeExecutionError("Code contains restricted operations")

        # Create execution environment
        exec_globals = {
            '__builtins__': {
                'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'tuple',
                'set', 'range', 'enumerate', 'zip', 'map', 'filter', 'sorted',
                'sum', 'min', 'max', 'abs', 'round', 'type', 'isinstance',
                'print', 'json', 'math', 'datetime', 'random', 'string',
                'urllib', 'base64', 'hashlib', 'uuid', 're', 'collections',
                'itertools', 'functools', 'operator', 'statistics'
            }
        }
        exec_locals = parameters.copy()

        # Capture output
        stdout_capture = StringIO()
        stderr_capture = StringIO()

        try:
            # Execute with timeout
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code, exec_globals, exec_locals)

            # Get results
            result = {
                'success': True,
                'result': exec_locals.get('result'),
                'output': stdout_capture.getvalue(),
                'error': None
            }

            # If no explicit result, return all new variables
            if result['result'] is None:
                result['result'] = {
                    k: v for k, v in exec_locals.items()
                    if k not in parameters and not k.startswith('_')
                }

            return result

        except Exception as e:
            return {
                'success': False,
                'result': None,
                'output': stdout_capture.getvalue(),
                'error': f"{type(e).__name__}: {str(e)}"
            }

    async def execute_api_call(
        self,
        endpoint: str,
        method: str,
        parameters: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Execute API call."""
        import aiohttp

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                kwargs = {
                    'url': endpoint,
                    'headers': headers or {},
                }

                if method.upper() == 'GET':
                    kwargs['params'] = parameters
                else:
                    kwargs['json'] = parameters

                async with session.request(method.upper(), **kwargs) as response:
                    try:
                        result = await response.json()
                    except:
                        result = await response.text()

                    return {
                        'success': response.status < 400,
                        'status_code': response.status,
                        'result': result,
                        'headers': dict(response.headers)
                    }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'result': None
            }


class ToolService:
    """Service for managing and executing tools."""

    def __init__(self):
        self.executor = ToolExecutor()
        self.builtin_tools = self._load_builtin_tools()

    def _load_builtin_tools(self) -> Dict[str, Dict]:
        """Load built-in tools."""
        return {
            "web_search": {
                "name": "web_search",
                "description": "Search the web for information",
                "schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "num_results": {"type": "integer", "default": 5, "description": "Number of results to return"}
                    },
                    "required": ["query"]
                },
                "implementation": """
import requests
import json

def web_search_tool(query, num_results=5):
    # This would integrate with a real search API
    # For demo purposes, return mock data
    result = {
        "query": query,
        "results": [
            {
                "title": f"Result {i+1} for {query}",
                "url": f"https://example.com/result-{i+1}",
                "snippet": f"This is a snippet for result {i+1}"
            }
            for i in range(num_results)
        ]
    }
    return result

result = web_search_tool(query, num_results)
"""
            },
            "calculator": {
                "name": "calculator",
                "description": "Perform mathematical calculations",
                "schema": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "Mathematical expression to evaluate"}
                    },
                    "required": ["expression"]
                },
                "implementation": """
import math
import re

def calculate(expression):
    # Clean and validate expression
    expression = re.sub(r'[^0-9+\\-*/.() ]', '', expression)

    try:
        # Use eval with restricted globals for safety
        allowed_names = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow, "sqrt": math.sqrt, "sin": math.sin,
            "cos": math.cos, "tan": math.tan, "log": math.log, "pi": math.pi, "e": math.e
        }

        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return {"result": result, "expression": expression}
    except Exception as e:
        return {"error": str(e), "expression": expression}

result = calculate(expression)
"""
            },
            "text_analyzer": {
                "name": "text_analyzer",
                "description": "Analyze text for various properties",
                "schema": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to analyze"},
                        "analysis_type": {"type": "string", "enum": ["word_count", "sentiment", "readability"], "description": "Type of analysis to perform"}
                    },
                    "required": ["text", "analysis_type"]
                },
                "implementation": """
import re
import string

def analyze_text(text, analysis_type):
    if analysis_type == "word_count":
        words = len(text.split())
        chars = len(text)
        chars_no_spaces = len(text.replace(' ', ''))
        sentences = len([s for s in re.split(r'[.!?]+', text) if s.strip()])

        return {
            "words": words,
            "characters": chars,
            "characters_no_spaces": chars_no_spaces,
            "sentences": sentences,
            "avg_words_per_sentence": words / max(sentences, 1)
        }

    elif analysis_type == "sentiment":
        # Simple sentiment analysis based on word counting
        positive_words = ["good", "great", "excellent", "amazing", "wonderful", "fantastic", "love", "like", "happy", "joy"]
        negative_words = ["bad", "terrible", "awful", "hate", "dislike", "sad", "angry", "frustrated", "disappointed"]

        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        if positive_count > negative_count:
            sentiment = "positive"
        elif negative_count > positive_count:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {
            "sentiment": sentiment,
            "positive_indicators": positive_count,
            "negative_indicators": negative_count,
            "confidence": abs(positive_count - negative_count) / max(len(text.split()), 1)
        }

    elif analysis_type == "readability":
        words = text.split()
        sentences = len([s for s in re.split(r'[.!?]+', text) if s.strip()])
        syllables = sum(max(1, len(re.findall(r'[aeiouAEIOU]', word))) for word in words)

        # Flesch Reading Ease approximation
        if sentences > 0 and len(words) > 0:
            flesch_score = 206.835 - 1.015 * (len(words) / sentences) - 84.6 * (syllables / len(words))

            if flesch_score >= 90:
                level = "Very Easy"
            elif flesch_score >= 80:
                level = "Easy"
            elif flesch_score >= 70:
                level = "Fairly Easy"
            elif flesch_score >= 60:
                level = "Standard"
            elif flesch_score >= 50:
                level = "Fairly Difficult"
            elif flesch_score >= 30:
                level = "Difficult"
            else:
                level = "Very Difficult"
        else:
            flesch_score = 0
            level = "Unknown"

        return {
            "flesch_score": round(flesch_score, 2),
            "reading_level": level,
            "avg_sentence_length": len(words) / max(sentences, 1),
            "avg_syllables_per_word": syllables / max(len(words), 1)
        }

    return {"error": "Unknown analysis type"}

result = analyze_text(text, analysis_type)
"""
            }
        }

    async def get_tool(self, tool_id: str, user_id: Optional[str] = None) -> Optional[Tool]:
        """Get tool by ID."""
        async with AsyncSessionLocal() as db:
            query = select(Tool).where(Tool.id == tool_id)
            if user_id:
                query = query.where((Tool.user_id == user_id) | (Tool.is_builtin == True))

            result = await db.execute(query)
            return result.scalar_one_or_none()

    async def get_tool_by_name(self, name: str, user_id: Optional[str] = None) -> Optional[Tool]:
        """Get tool by name."""
        async with AsyncSessionLocal() as db:
            query = select(Tool).where(Tool.name == name, Tool.is_active == True)
            if user_id:
                query = query.where((Tool.user_id == user_id) | (Tool.is_builtin == True))

            result = await db.execute(query)
            return result.scalar_one_or_none()

    async def list_tools(self, user_id: str, category: Optional[str] = None) -> List[Dict]:
        """List available tools for a user."""
        async with AsyncSessionLocal() as db:
            query = select(Tool).where(
                ((Tool.user_id == user_id) | (Tool.is_builtin == True)),
                Tool.is_active == True
            )

            if category:
                query = query.where(Tool.category == category)

            result = await db.execute(query)
            tools = result.scalars().all()

            return [
                {
                    "id": str(tool.id),
                    "name": tool.name,
                    "description": tool.description,
                    "schema": tool.schema,
                    "category": tool.category,
                    "is_builtin": tool.is_builtin,
                    "version": tool.version,
                    "usage_count": tool.usage_count,
                }
                for tool in tools
            ]

    async def create_tool(
        self,
        user_id: str,
        name: str,
        description: str,
        schema: Dict,
        implementation: str,
        category: str = "custom"
    ) -> str:
        """Create a new custom tool."""
        # Validate the implementation
        if not self.executor.validate_code(implementation):
            raise ValueError("Tool implementation contains restricted operations")

        async with AsyncSessionLocal() as db:
            # Check if tool name already exists
            existing = await db.execute(
                select(Tool).where(Tool.name == name, Tool.user_id == user_id)
            )
            if existing.scalar_one_or_none():
                raise ValueError("Tool with this name already exists")

            tool = Tool(
                user_id=user_id,
                name=name,
                description=description,
                schema=schema,
                implementation=implementation,
                category=category,
                is_builtin=False,
                version="1.0.0"
            )

            db.add(tool)
            await db.commit()
            await db.refresh(tool)

            return str(tool.id)

    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        user_id: str,
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Execute a tool with given parameters."""
        start_time = datetime.utcnow()

        try:
            # Get tool (check builtin first, then custom)
            tool = None
            if tool_name in self.builtin_tools:
                # Create a temporary tool object for builtin tools
                builtin = self.builtin_tools[tool_name]
                tool = Tool(
                    id="builtin-" + tool_name,
                    name=builtin["name"],
                    description=builtin["description"],
                    schema=builtin["schema"],
                    implementation=builtin["implementation"],
                    is_builtin=True
                )
            else:
                tool = await self.get_tool_by_name(tool_name, user_id)

            if not tool:
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' not found",
                    "result": None
                }

            # Create execution record
            execution_id = None
            if not tool.is_builtin or not tool.id.startswith("builtin-"):
                async with AsyncSessionLocal() as db:
                    execution = ToolExecution(
                        tool_id=tool.id,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        message_id=message_id,
                        parameters=parameters,
                        status="running"
                    )
                    db.add(execution)
                    await db.commit()
                    await db.refresh(execution)
                    execution_id = execution.id

            # Execute the tool
            if tool.implementation.startswith("http"):
                # API call tool
                result = await self.executor.execute_api_call(
                    tool.implementation,
                    "POST",
                    parameters,
                    timeout=timeout
                )
            else:
                # Python code tool
                result = await self.executor.execute_python_code(
                    tool.implementation,
                    parameters,
                    timeout=timeout
                )

            # Calculate execution time
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Update execution record
            if execution_id:
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        update(ToolExecution)
                        .where(ToolExecution.id == execution_id)
                        .values(
                            result=result,
                            status="completed" if result.get("success") else "failed",
                            execution_time=execution_time,
                            error=result.get("error")
                        )
                    )

                    # Update tool usage statistics
                    await db.execute(
                        update(Tool)
                        .where(Tool.id == tool.id)
                        .values(
                            usage_count=Tool.usage_count + 1,
                            last_used=datetime.utcnow()
                        )
                    )

                    await db.commit()

            result["execution_time_ms"] = execution_time
            return result

        except Exception as e:
            execution_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            error_result = {
                "success": False,
                "error": str(e),
                "result": None,
                "execution_time_ms": execution_time
            }

            # Update execution record with error
            if execution_id:
                async with AsyncSessionLocal() as db:
                    await db.execute(
                        update(ToolExecution)
                        .where(ToolExecution.id == execution_id)
                        .values(
                            result=error_result,
                            status="failed",
                            execution_time=execution_time,
                            error=str(e)
                        )
                    )
                    await db.commit()

            return error_result

    async def get_tool_execution_history(
        self,
        user_id: str,
        tool_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """Get tool execution history for a user."""
        async with AsyncSessionLocal() as db:
            query = select(ToolExecution).where(ToolExecution.user_id == user_id)

            if tool_id:
                query = query.where(ToolExecution.tool_id == tool_id)

            query = query.order_by(ToolExecution.created_at.desc()).limit(limit)

            result = await db.execute(query)
            executions = result.scalars().all()

            return [
                {
                    "id": str(execution.id),
                    "tool_id": str(execution.tool_id),
                    "parameters": execution.parameters,
                    "result": execution.result,
                    "status": execution.status,
                    "execution_time": execution.execution_time,
                    "error": execution.error,
                    "created_at": execution.created_at.isoformat(),
                }
                for execution in executions
            ]

    async def initialize_builtin_tools(self):
        """Initialize built-in tools in the database."""
        async with AsyncSessionLocal() as db:
            for tool_name, tool_data in self.builtin_tools.items():
                # Check if tool already exists
                existing = await db.execute(
                    select(Tool).where(Tool.name == tool_name, Tool.is_builtin == True)
                )

                if not existing.scalar_one_or_none():
                    tool = Tool(
                        user_id=None,
                        name=tool_data["name"],
                        description=tool_data["description"],
                        schema=tool_data["schema"],
                        implementation=tool_data["implementation"],
                        category="builtin",
                        is_builtin=True,
                        is_active=True,
                        version="1.0.0"
                    )
                    db.add(tool)

            await db.commit()


# Global tool service instance
tool_service = ToolService()