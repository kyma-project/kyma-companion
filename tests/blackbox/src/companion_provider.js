/**
 * Custom Promptfoo provider for Kyma Companion API
 *
 * This provider implements the Promptfoo provider interface to call the
 * Kyma Companion API and return structured responses for evaluation.
 */

const axios = require('axios');

/**
 * CompanionProvider class implements the custom provider interface for Promptfoo
 */
class CompanionProvider {
  constructor(options) {
    this.id = () => 'companion';
    this.apiUrl = options.config?.apiUrl || process.env.COMPANION_API_URL || 'http://localhost:8000';
    this.resource = options.config?.resource || {};
    this.conversationId = null;

    // Authentication headers
    this.companionToken = process.env.COMPANION_TOKEN || '';
    this.clusterCaData = process.env.TEST_CLUSTER_CA_DATA || '';
    this.clusterUrl = process.env.TEST_CLUSTER_URL || '';
    this.clusterAuthToken = process.env.TEST_CLUSTER_AUTH_TOKEN || '';
  }

  /**
   * Get authentication headers for Companion API
   */
  getHeaders(sessionId = null) {
    const headers = {
      'Authorization': `Bearer ${this.companionToken}`,
      'X-Cluster-Certificate-Authority-Data': this.clusterCaData,
      'X-Cluster-Url': this.clusterUrl,
      'X-K8s-Authorization': this.clusterAuthToken,
      'Content-Type': 'application/json',
    };

    if (sessionId) {
      headers['session-id'] = sessionId;
    }

    return headers;
  }

  /**
   * Initialize a new conversation with the Companion API
   */
  async initializeConversation() {
    try {
      const payload = {
        query: '',
        resource_kind: this.resource.kind || '',
        resource_api_version: this.resource.api_version || '',
        resource_name: this.resource.name || '',
        namespace: this.resource.namespace || '',
      };

      const response = await axios.post(
        `${this.apiUrl}/api/conversations`,
        payload,
        { headers: this.getHeaders() }
      );

      this.conversationId = response.data.conversation_id;
      return {
        conversationId: this.conversationId,
        initialQuestions: response.data.initial_questions || [],
      };
    } catch (error) {
      throw new Error(`Failed to initialize conversation: ${error.message}`);
    }
  }

  /**
   * Parse SSE (Server-Sent Events) stream response
   */
  parseSSEChunk(line) {
    try {
      // SSE format: chunks are newline-delimited JSON objects
      if (!line || line.trim() === '') {
        return null;
      }
      return JSON.parse(line);
    } catch (error) {
      // Skip non-JSON lines (e.g., SSE comments)
      return null;
    }
  }

  /**
   * Extract final answer and metadata from SSE stream
   */
  extractResponseFromChunks(chunks) {
    if (!chunks || chunks.length === 0) {
      throw new Error('No response chunks received');
    }

    // Get the last chunk which should contain the final answer
    const lastChunk = chunks[chunks.length - 1];

    if (!lastChunk || !lastChunk.data) {
      throw new Error('Invalid response structure: no data in last chunk');
    }

    if (lastChunk.data.error) {
      throw new Error(`Companion API error: ${lastChunk.data.error}`);
    }

    if (!lastChunk.data.answer || !lastChunk.data.answer.content) {
      throw new Error('No answer content in response');
    }

    // Extract all tasks and tool calls from chunks
    const tasks = [];
    const toolCalls = new Set();
    const agents = new Set();

    for (const chunk of chunks) {
      if (chunk.data && chunk.data.answer && chunk.data.answer.tasks) {
        for (const task of chunk.data.answer.tasks) {
          tasks.push(task);

          // Extract tool name from task_name if it looks like a tool call
          // Task names often have format like "calling_tool_name" or similar
          if (task.task_name) {
            // Common tool names in Kyma Companion
            const toolPatterns = [
              'kyma_query_tool',
              'k8s_query_tool',
              'search_kyma_doc',
              'fetch_kyma_resource_version',
              'fetch_pod_logs_tool'
            ];

            for (const tool of toolPatterns) {
              if (task.task_name.toLowerCase().includes(tool.toLowerCase())) {
                toolCalls.add(tool);
              }
            }
          }

          if (task.agent) {
            agents.add(task.agent);
          }
        }
      }
    }

    return {
      answer: lastChunk.data.answer.content,
      tasks: tasks,
      toolCalls: Array.from(toolCalls),
      agents: Array.from(agents),
      chunks: chunks,
    };
  }

  /**
   * Send a query to the Companion API and get the response
   *
   * This is the main method called by Promptfoo
   */
  async callApi(prompt) {
    try {
      // Initialize conversation if not already done
      if (!this.conversationId) {
        await this.initializeConversation();
      }

      const payload = {
        query: prompt,
        resource_kind: this.resource.kind || '',
        resource_api_version: this.resource.api_version || '',
        resource_name: this.resource.name || '',
        namespace: this.resource.namespace || '',
      };

      // Send query to Companion
      const response = await axios.post(
        `${this.apiUrl}/api/conversations/${this.conversationId}/messages`,
        payload,
        {
          headers: this.getHeaders(this.conversationId),
          responseType: 'stream',
          timeout: 600000, // 10 minutes timeout
        }
      );

      // Collect all chunks from the SSE stream
      const chunks = [];

      return new Promise((resolve, reject) => {
        let buffer = '';

        response.data.on('data', (chunk) => {
          buffer += chunk.toString();

          // Process complete lines
          const lines = buffer.split('\n');
          buffer = lines.pop() || ''; // Keep the incomplete line in buffer

          for (const line of lines) {
            const parsed = this.parseSSEChunk(line);
            if (parsed) {
              chunks.push(parsed);
            }
          }
        });

        response.data.on('end', () => {
          // Process any remaining data in buffer
          if (buffer.trim()) {
            const parsed = this.parseSSEChunk(buffer);
            if (parsed) {
              chunks.push(parsed);
            }
          }

          try {
            const result = this.extractResponseFromChunks(chunks);

            // Return in Promptfoo format
            resolve({
              output: result.answer,
              metadata: {
                conversationId: this.conversationId,
                tasks: result.tasks,
                toolCalls: result.toolCalls,
                agents: result.agents,
                chunks: result.chunks,
              },
            });
          } catch (error) {
            reject(error);
          }
        });

        response.data.on('error', (error) => {
          reject(new Error(`Stream error: ${error.message}`));
        });
      });

    } catch (error) {
      if (error.response) {
        throw new Error(
          `Companion API error (${error.response.status}): ${error.response.data}`
        );
      }
      throw new Error(`Failed to call Companion API: ${error.message}`);
    }
  }
}

/**
 * Promptfoo provider factory function
 * This is the main export that Promptfoo will call
 */
module.exports = class CompanionProviderWrapper {
  constructor(options) {
    this.provider = new CompanionProvider(options);
  }

  id() {
    return 'companion';
  }

  async callApi(prompt, context) {
    return this.provider.callApi(prompt);
  }
};
