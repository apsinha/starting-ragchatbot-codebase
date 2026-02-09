import anthropic
from typing import List, Optional


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    MAX_TOOL_ROUNDS = 2

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for course information.

Tool Selection:
- Use **get_course_outline** for questions about course structure, what lessons a course contains, or course overviews. This tool returns the course title, course link, and each lesson's number and title.
- Use **search_course_content** for questions about specific course content, concepts, or detailed educational materials.
- **Up to 2 tool calls per query** — you may call tools sequentially when a question requires combining information (e.g., first get a course outline, then search content based on what you learned)
- Synthesize tool results into accurate, fact-based responses
- If a tool yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without using tools
- **Course structure questions** (e.g. "What lessons are in...", "Show me the outline of..."): Use get_course_outline
- **Course content questions**: Use search_course_content
- When presenting outline results, include the course title, course link, and the number and title of each lesson
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, search explanations, or question-type analysis
 - Do not mention "based on the search results"


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def _execute_tools(self, response, tool_manager) -> list:
        """Execute all tool calls in a response and return tool_result messages."""
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                try:
                    result = tool_manager.execute_tool(block.name, **block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )
                except Exception as e:
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(e),
                            "is_error": True,
                        }
                    )
        return tool_results

    def _extract_text(self, response) -> Optional[str]:
        """Extract the first text block from a response."""
        for block in response.content:
            if block.type == "text":
                return block.text
        return None

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context.
        Supports up to MAX_TOOL_ROUNDS sequential tool-call rounds.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Build messages list
        messages = [{"role": "user", "content": query}]

        # Prepare API call parameters
        api_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content,
        }

        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        # Initial API call
        response = self.client.messages.create(**api_params)

        # Loop for up to MAX_TOOL_ROUNDS of tool execution
        for round in range(self.MAX_TOOL_ROUNDS):
            if response.stop_reason != "tool_use" or not tool_manager:
                break

            # Append assistant's tool-use response
            messages.append({"role": "assistant", "content": response.content})

            # Execute tools and append results
            tool_results = self._execute_tools(response, tool_manager)
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            # Build follow-up call params
            follow_up_params = {
                **self.base_params,
                "messages": messages,
                "system": system_content,
            }

            # Keep tools attached on intermediate rounds, strip on final round
            if round < self.MAX_TOOL_ROUNDS - 1 and tools:
                follow_up_params["tools"] = tools
                follow_up_params["tool_choice"] = {"type": "auto"}

            response = self.client.messages.create(**follow_up_params)

        # Extract text from response
        text = self._extract_text(response)
        return (
            text
            or "I wasn't able to generate a response. Please try rephrasing your question."
        )
