# Bot Prompting System

## Overview

The Mumble AI bot uses a sophisticated prompting system that combines multiple context layers, anti-hallucination measures, and intelligent memory retrieval to generate accurate, contextual responses. The system is designed to prevent repetitive responses, maintain conversation flow, and provide truthful information based on stored memories.

## Prompt Architecture

### Multi-Layer Context System

The bot's prompt is constructed with three distinct context layers:

#### 1. **System Instructions Layer**
- **Anti-hallucination rules**: Prevent the bot from making up information
- **Brevity guidelines**: Keep responses concise (1-2 sentences)
- **Behavioral constraints**: No emojis, no repetition, no summaries
- **Truthfulness requirements**: Admit uncertainty rather than guess

#### 2. **Memory Context Layer**
- **Persistent memories**: Important saved information (schedules, facts, preferences)
- **Semantic context**: Similar past conversations for understanding
- **Current conversation**: Recent exchanges in the current session

#### 3. **Current Input Layer**
- **User's current message**: The immediate input to respond to
- **Response prompt**: "You:" to indicate where the bot should respond

## Prompt Construction Process

### Step 1: System Instructions

The bot starts with strict behavioral rules:

```
You are having a natural, flowing conversation. CRITICAL RULES - FOLLOW EXACTLY:

1. BREVITY: Keep responses to 1-2 short sentences maximum. Be conversational but concise.
2. TRUTH: NEVER make up information. If you don't know something, say "I don't know" or "I'm not sure."
3. NO HALLUCINATION: Do NOT invent schedules, events, plans, or details that weren't mentioned by the user.
4. NO EMOJIS: Never use emojis in your responses.
5. NO REPETITION: Do NOT repeat or rephrase what you just said in previous messages.
6. NO SUMMARIES: Do NOT summarize the conversation.
7. BUILD NATURALLY: Add new information or perspectives, don't restate previous points.
8. STAY GROUNDED: Only discuss things that were actually mentioned in the conversation.
9. RESPOND TO CURRENT MESSAGE: Focus ONLY on what the user just said. Do NOT bring up unrelated topics from past conversations.
```

### Step 2: Personality Configuration

If a bot persona is configured, it's added with truthfulness priority:

```python
if persona and persona.strip():
    full_prompt += f"Your personality/character: {persona.strip()}\n\n"
    full_prompt += "IMPORTANT: Stay in character BUT prioritize truthfulness over role-playing. "
    full_prompt += "If you don't have information, admit it rather than making something up to fit your character.\n\n"
```

### Step 3: Persistent Memory Integration

The bot retrieves and includes important saved information:

```python
# Get top 10 most important memories for the user
persistent_memories = self.get_persistent_memories(user_name, limit=10)

if persistent_memories:
    full_prompt += "IMPORTANT SAVED INFORMATION (use this to answer questions accurately):\n"
    for mem in persistent_memories:
        category_label = mem['category'].upper()
        full_prompt += f"[{category_label}] {mem['content']}\n"
    full_prompt += "\nUse this information to answer questions. If asked about schedules, tasks, or facts, refer to the saved information above.\n\n"
```

### Step 4: Semantic Context Retrieval

Similar past conversations are retrieved using semantic similarity:

```python
# Get semantically similar past conversations
long_term_memory = self.get_semantic_context(
    current_message, user_name, session_id, limit=long_term_limit
)

if long_term_memory:
    full_prompt += "BACKGROUND CONTEXT (for understanding only - DO NOT bring up these old topics unless directly asked):\n"
    for mem in long_term_memory:
        role_label = "User" if mem['role'] == 'user' else "You"
        full_prompt += f"{role_label}: {mem['message']}\n"
    full_prompt += "\nREMEMBER: This background context is ONLY for understanding the user better. Focus on their CURRENT message, NOT old topics.\n\n"
```

### Step 5: Current Session Context

Recent exchanges in the current session are included:

```python
# Get short-term memory (current session)
short_term_memory = self.get_conversation_history(session_id=session_id, limit=short_term_limit)

if short_term_memory:
    full_prompt += "Current conversation:\n"
    for role, message, msg_type, timestamp in short_term_memory:
        if role == 'user':
            full_prompt += f"User: {message}\n"
        else:
            full_prompt += f"You: {message}\n"
    full_prompt += "\n"
```

### Step 6: Current Input

The user's current message is added with response prompt:

```python
# Add current message
full_prompt += f"User: {current_message}\nYou:"
```

## Anti-Hallucination Measures

### Core Principles

1. **Truthfulness First**: Never make up information
2. **Admit Uncertainty**: Say "I don't know" rather than guess
3. **Ground in Reality**: Only discuss actually mentioned topics
4. **Focus on Current Input**: Don't bring up unrelated past topics
5. **No Repetition**: Don't repeat previous responses
6. **No Summaries**: Don't summarize conversations

### Implementation Strategies

#### 1. **Explicit Instructions**
The prompt includes clear, direct instructions against hallucination:

```
2. TRUTH: NEVER make up information. If you don't know something, say "I don't know" or "I'm not sure."
3. NO HALLUCINATION: Do NOT invent schedules, events, plans, or details that weren't mentioned by the user.
```

#### 2. **Memory-Based Responses**
The bot uses stored memories to provide factual information:

```
IMPORTANT SAVED INFORMATION:
[SCHEDULE] Funeral at church on Monday at 9am
[FACT] Lives in New York City
[PREFERENCE] Prefers tea over coffee
```

#### 3. **Context Separation**
Different context types are clearly labeled to prevent confusion:

- **IMPORTANT SAVED INFORMATION**: For factual recall
- **BACKGROUND CONTEXT**: For understanding only
- **Current conversation**: For immediate context

#### 4. **Response Constraints**
The bot is constrained to focus on the current message:

```
9. RESPOND TO CURRENT MESSAGE: Focus ONLY on what the user just said. Do NOT bring up unrelated topics from past conversations.
```

## Memory Integration

### Persistent Memory Usage

The bot uses persistent memories to answer factual questions:

```
User: "What do I have scheduled for Monday?"
Bot retrieves: [SCHEDULE] Funeral at church on Monday at 9am
Bot responds: "You have a funeral at the church on Monday at 9am."
```

### Semantic Context Usage

Background context helps the bot understand user patterns:

```
BACKGROUND CONTEXT (for understanding only):
User: I love Italian food
You: That's great! What's your favorite Italian dish?
User: I really enjoy pasta
```

This context helps the bot understand the user's preferences without explicitly bringing up old topics.

### Session Context Usage

Current conversation maintains flow:

```
Current conversation:
User: Good morning!
You: Good morning! How are you?
User: What do I have Monday?
You:
```

## Response Generation

### Ollama Configuration

The bot uses specific Ollama settings for optimal responses:

```python
response = requests.post(
    f"{ollama_url}/api/generate",
    json={
        'model': ollama_model,
        'prompt': prompt,
        'stream': False,
        'options': {
            'temperature': 0.7,  # Balanced creativity and consistency
            'top_p': 0.9,        # Nucleus sampling for quality
            'num_predict': 100,  # Limit response length
            'stop': ['\n\n', 'User:', 'Assistant:']  # Stop at conversation breaks
        }
    },
    timeout=60
)
```

### Response Constraints

- **Length limit**: 100 tokens maximum (roughly 1-2 sentences)
- **Stop sequences**: Prevents runaway responses
- **Temperature**: Balanced for natural but consistent responses
- **Nucleus sampling**: Ensures quality token selection

## Prompt Engineering Best Practices

### 1. **Clear Role Definition**
The bot's role is clearly defined in the prompt:

```
You are having a natural, flowing conversation.
```

### 2. **Explicit Constraints**
All behavioral constraints are explicitly stated:

```
CRITICAL RULES - FOLLOW EXACTLY:
1. BREVITY: Keep responses to 1-2 short sentences maximum.
2. TRUTH: NEVER make up information.
```

### 3. **Context Hierarchy**
Different context types are clearly separated:

- **System instructions**: Behavioral rules
- **Personality**: Character definition
- **Important information**: Factual memories
- **Background context**: Understanding context
- **Current conversation**: Immediate context
- **Current input**: User's message

### 4. **Memory Integration**
Memories are integrated with clear usage instructions:

```
Use this information to answer questions. If asked about schedules, tasks, or facts, refer to the saved information above.
```

### 5. **Anti-Repetition Measures**
The bot is explicitly instructed against repetition:

```
5. NO REPETITION: Do NOT repeat or rephrase what you just said in previous messages.
6. NO SUMMARIES: Do NOT summarize the conversation.
7. BUILD NATURALLY: Add new information or perspectives, don't restate previous points.
```

## Configuration Options

### Memory Limits

Configurable through database settings:

- `short_term_memory_limit`: Number of recent exchanges (default: 3)
- `long_term_memory_limit`: Number of similar past conversations (default: 3)
- `semantic_similarity_threshold`: Minimum similarity for context (default: 0.7)

### Response Parameters

- `temperature`: Creativity vs consistency (default: 0.7)
- `top_p`: Nucleus sampling threshold (default: 0.9)
- `num_predict`: Maximum response length (default: 100)
- `stop`: Stop sequences for response termination

### Bot Persona

Configurable personality that respects truthfulness:

```python
persona = self.get_config('bot_persona', '')
if persona and persona.strip():
    full_prompt += f"Your personality/character: {persona.strip()}\n\n"
    full_prompt += "IMPORTANT: Stay in character BUT prioritize truthfulness over role-playing.\n\n"
```

## Error Handling

### Fallback Mechanisms

If prompt construction fails:

```python
except Exception as e:
    logger.error(f"Error building prompt with context: {e}")
    # Fallback to just the current message if there's an error
    return current_message
```

### Service Failures

The bot includes circuit breakers for external services:

```python
def get_ollama_response(self, text, user_name=None, session_id=None):
    try:
        return self.ollama_circuit_breaker.call(self._get_ollama_response_internal, text, user_name, session_id)
    except CircuitBreakerError:
        logger.error("Ollama circuit breaker is open, cannot get response")
        return "Sorry, I am temporarily unavailable due to service issues."
```

## Performance Optimization

### Prompt Size Management

- **Memory limits**: Prevent prompt overflow
- **Context filtering**: Only include relevant information
- **Response length limits**: Control output size
- **Stop sequences**: Prevent runaway generation

### Caching Strategies

- **Embedding cache**: Reduce API calls for repeated text
- **Session tracking**: In-memory session management
- **Connection pooling**: Database connection reuse

## Monitoring and Debugging

### Logging

The bot logs prompt construction and response generation:

```python
logger.info(f"Retrieved {len(persistent_memories)} persistent memories for {user_name}")
logger.debug(f"Adding memory to prompt: [{category_label}] {mem['content']}")
```

### Health Monitoring

Continuous monitoring of:

- **Ollama service**: LLM availability and performance
- **Database**: Memory retrieval and storage
- **Response times**: Generation latency
- **Error rates**: Service failure tracking

## Troubleshooting

### Common Issues

1. **Repetitive responses**: Check anti-repetition rules in prompt
2. **Hallucination**: Verify memory integration and truthfulness rules
3. **Context overflow**: Adjust memory limits and similarity thresholds
4. **Poor responses**: Check Ollama configuration and prompt structure

### Debugging Tools

1. **Log analysis**: Detailed prompt construction logging
2. **Memory inspection**: Database queries for memory content
3. **Response analysis**: Generated response quality assessment
4. **Service monitoring**: External service health checks

This prompting system ensures the Mumble AI bot provides accurate, contextual, and engaging conversations while maintaining truthfulness and preventing hallucination through careful prompt engineering and multi-layered memory integration.
