from typing import Any, Iterator, List, Optional
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.outputs import ChatGenerationChunk
from llm_commons.langchain.proxy import ChatOpenAI
from helpers.models import create_model, LLM_AZURE_GPT4_32K_STREAMING, AICORE_CONFIGURATION_ID_GPT4, AICORE_DEPLOYMENT_ID_GPT4
from langchain_core.messages import BaseMessage
import tiktoken


class MultiModelClient(ChatOpenAI):
    _gpt4_32k: ChatOpenAI = create_model(LLM_AZURE_GPT4_32K_STREAMING)
    _encoding: tiktoken.Encoding = tiktoken.get_encoding("cl100k_base")

    def __init__(self):
        super().__init__(deployment_id=AICORE_DEPLOYMENT_ID_GPT4,
                          config_id=AICORE_CONFIGURATION_ID_GPT4)

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Run the LLM on the given input.

        Override this method to implement the LLM logic.

        Args:
            prompt: The prompt to generate from.
            stop: Stop words to use when generating. Model output is cut off at the
                first occurrence of any of the stop substrings.
                If stop tokens are not supported consider raising NotImplementedError.
            run_manager: Callback manager for the run.
            **kwargs: Arbitrary additional keyword arguments. These are usually passed
                to the model provider API call.

        Returns:
            The model output as a string. Actual completions SHOULD NOT include the prompt.
        """
        if stop is not None:
            raise ValueError("stop kwargs are not permitted.")
        context_length = len(self._encoding.encode(prompt))
        if context_length < 4000:
            return super().invoke(prompt, stop=stop)
        return self._gpt4_32k.invoke(prompt, stop=stop)

    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """Stream the LLM on the given prompt.

        This method should be overridden by subclasses that support streaming.

        If not implemented, the default behavior of calls to stream will be to
        fallback to the non-streaming version of the model and return
        the output as a single chunk.

        Args:
            messages: The prompt to generate from.
            stop: Stop words to use when generating. Model output is cut off at the
                first occurrence of any of these substrings.
            run_manager: Callback manager for the run.
            **kwargs: Arbitrary additional keyword arguments. These are usually passed
                to the model provider API call.

        Returns:
            An iterator of ChatGenerationChunk.
        """
        context_length = len(self._encoding.encode(messages[0].content))
        if context_length > 4000:
            for chunk in self._gpt4_32k._stream(messages, stop=stop, run_manager=run_manager):
                yield chunk
        else:
            for chunk in super()._stream(messages, stop=stop, run_manager=run_manager):
                yield chunk

    @property
    def _llm_type(self) -> str:
        """Get the type of language model used by this chat model. Used for logging purposes only."""
        return "custom"
