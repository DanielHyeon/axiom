import React, { useState } from 'react';
import { apiClient } from '../../lib/api-client';

export const NL2SQLPage: React.FC = () => {
    const [prompt, setPrompt] = useState("");
    const [response, setResponse] = useState("");
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);
        setResponse("");

        // Simulate initial planner response smoothly
        setTimeout(() => {
            setResponse((prev) => prev + "Agent Event: [Planning] Constructing target schema lookups...\n");
        }, 500);

        try {
            // Connects to Oracle Text2SQL API logic
            const res = await apiClient.post('/oracle/text2sql/react', {
                natural_language_query: prompt,
                target_db: "synapse"
            });
            setResponse((prev) => prev + "\nAgent Final Response:\n" + JSON.stringify(res.data, null, 2));
        } catch (err: any) {
            const errorDetail = err?.response?.data || err.message;
            setResponse((prev) => prev + `\nAgent Execution Failed:\n${JSON.stringify(errorDetail, null, 2)}`);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-white rounded shadow">
            {/* Header */}
            <div className="p-4 border-b">
                <h1 className="text-2xl font-bold text-gray-800">NL-to-SQL Agent</h1>
                <p className="text-gray-500 text-sm">Query your Synapse and Enterprise databases using Natural Language.</p>
            </div>

            {/* Chat History Mock */}
            <div className="flex-1 p-4 overflow-auto bg-gray-50">
                {response && (
                    <div className="mb-4 bg-white p-4 rounded border border-gray-200">
                        <span className="font-bold text-indigo-600 block mb-2">Oracle Response:</span>
                        <pre className="text-sm whitespace-pre-wrap">{response}</pre>
                    </div>
                )}
            </div>

            {/* Input Area */}
            <div className="p-4 border-t bg-white">
                <form onSubmit={handleSubmit} className="flex gap-2">
                    <input
                        type="text"
                        placeholder="E.g., 'Show me sales figures for Q4'"
                        className="flex-1 border border-gray-300 rounded p-2 focus:ring-2 focus:ring-blue-500"
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                    />
                    <button
                        type="submit"
                        disabled={loading || !prompt.trim()}
                        className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-6 rounded disabled:opacity-50"
                    >
                        {loading ? "Generating..." : "Ask Oracle"}
                    </button>
                </form>
            </div>
        </div>
    );
};
