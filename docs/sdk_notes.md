# Verified SDK Notes (`multi-provider-llm-chatbot`)

## 1. Google GenAI SDK (`google-genai`)
- Import: `from google import genai` and `from google.genai import types`, `from google.genai import errors as genai_errors`
- Client construction: `client = genai.Client(api_key=api_key)`
- Generation call:
  ```python
  response = client.models.generate_content(
      model="gemini-2.5-flash",
      contents=contents,
      config=types.GenerateContentConfig(
          system_instruction=system_prompt,
          response_mime_type="application/json",
          temperature=0.2,
          max_output_tokens=1024,
      ),
  )
  ```
- Usage extraction:
  - `input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0`
  - `output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0`
- Error handling: catch `genai_errors.APIError as exc`; check `exc.code` (`429`, `500`, `503` -> retryable; `400`, `401`, `403` -> non-retryable).

## 2. Anthropic SDK (`anthropic`) — Offline Mock-Tested Adapter
- Import: `import anthropic`
- Client construction: `client = anthropic.Anthropic(api_key=api_key)`
- Generation call:
  ```python
  response = client.messages.create(
      model="claude-3-5-haiku-latest",
      max_tokens=1024,
      system=system_prompt,
      messages=messages,
  )
  raw_text = response.content[0].text
  input_tokens = response.usage.input_tokens
  output_tokens = response.usage.output_tokens
  ```

## 3. OpenAI SDK (`openai`) — Offline Mock-Tested Adapter
- Import: `import openai`
- Client construction: `client = openai.OpenAI(api_key=api_key)`
- Generation call:
  ```python
  response = client.chat.completions.create(
      model="gpt-4o-mini",
      response_format={"type": "json_object"},
      messages=[{"role": "system", "content": system_prompt}, *messages],
  )
  raw_text = response.choices[0].message.content or "{}"
  input_tokens = response.usage.prompt_tokens if response.usage else 0
  output_tokens = response.usage.completion_tokens if response.usage else 0
  ```
