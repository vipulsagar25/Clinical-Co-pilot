import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Send, Activity, Stethoscope, AlertTriangle, User, Bot, Loader2 } from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [messages, setMessages] = useState(() => {
    const saved = localStorage.getItem('chat_messages');
    return saved ? JSON.parse(saved) : [{
      role: 'assistant',
      content: 'Hello, I am the Clinical Co-pilot. How can I assist you with clinical guidelines today?'
    }];
  });

  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
    // Save to local storage on change
    localStorage.setItem('chat_messages', JSON.stringify(messages));
  }, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputMessage.trim()) return;

    const userMessage = { role: 'user', content: inputMessage };
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      // Send chat request
      // We'll pass user_id = 'demo_user' for now. We can handle actual state tracking via API later
      const response = await axios.post(`${API_BASE_URL}/chat`, {
        user_id: 'demo_user',
        message: userMessage.content
      });

      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: response.data.response }
      ]);

    } catch (error) {
      console.error("Error connecting to backend:", error);
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: "⚠️ Sorry, I encountered an error connecting to the server. Please ensure the backend is running on port 8000." }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([{
      role: 'assistant',
      content: 'Hello, I am the Clinical Co-pilot. How can I assist you with clinical guidelines today?'
    }]);
    localStorage.removeItem('chat_messages');
  };

  return (
    <div className="flex flex-col h-screen bg-slate-50 font-sans text-slate-900 w-full overflow-hidden">

      {/* Header */}
      <header className="flex items-center justify-between px-6 py-4 bg-white border-b border-slate-200 shadow-sm z-10 sticky top-0">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-600 text-white rounded-lg shadow-md flex items-center justify-center">
            <Stethoscope size={24} />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-800">Clinical Co-pilot</h1>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">IMCI Guidelines Assistant</p>
          </div>
        </div>

        <button
          onClick={clearChat}
          className="px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-md transition-colors"
        >
          Clear Chat
        </button>
      </header>

      {/* Main Chat Area */}
      <main className="flex-1 overflow-y-auto p-4 md:p-6 w-full max-w-4xl mx-auto scroll-smooth">
        <div className="space-y-6 flex flex-col pb-4">

          {messages.map((msg, index) => {
            const isUser = msg.role === 'user';
            // Detect danger signs visually
            const isEmergency = typeof msg.content === 'string' && msg.content.includes('⚠️ DANGER SIGNS DETECTED');

            return (
              <div key={index} className={`flex gap-4 ${isUser ? 'flex-row-reverse' : ''}`}>

                {/* Avatar */}
                <div className={`shrink-0 w-10 h-10 rounded-full flex items-center justify-center shadow-md ${isUser ? 'bg-indigo-600 text-white' :
                    isEmergency ? 'bg-red-100 text-red-600 border border-red-200' : 'bg-blue-100 text-blue-600 border border-blue-200'
                  }`}>
                  {isUser ? <User size={20} /> : isEmergency ? <AlertTriangle size={20} /> : <Bot size={20} />}
                </div>

                {/* Message Bubble */}
                <div className={`max-w-[85%] md:max-w-[75%] rounded-2xl p-5 shadow-sm ${isUser
                    ? 'bg-indigo-600 text-white rounded-tr-sm'
                    : isEmergency
                      ? 'bg-red-50 text-red-900 border border-red-200 rounded-tl-sm ring-1 ring-red-100'
                      : 'bg-white text-slate-800 border border-slate-200 rounded-tl-sm'
                  }`}>

                  {isEmergency && (
                    <div className="flex items-center gap-2 mb-2 font-bold text-red-700 uppercase tracking-wide text-xs">
                      <AlertTriangle size={14} className="animate-pulse" />
                      Critical Alert
                    </div>
                  )}

                  <div className="whitespace-pre-wrap leading-relaxed text-[15px]">
                    {msg.content}
                  </div>
                </div>

              </div>
            );
          })}

          {/* Loading Indicator */}
          {isLoading && (
            <div className="flex gap-4">
              <div className="shrink-0 w-10 h-10 rounded-full bg-blue-100 text-blue-600 border border-blue-200 flex items-center justify-center shadow-md animate-pulse">
                <Bot size={20} />
              </div>
              <div className="bg-white text-slate-800 border border-slate-200 rounded-2xl rounded-tl-sm p-5 shadow-sm flex items-center gap-2">
                <Loader2 size={16} className="animate-spin text-blue-500" />
                <span className="text-sm font-medium text-slate-500">Analyzing clinical guidelines...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Input Area */}
      <footer className="bg-white border-t border-slate-200 p-4 sticky bottom-0 z-10">
        <div className="max-w-4xl mx-auto flex items-end gap-3 rounded-xl bg-slate-50 border border-slate-200 focus-within:ring-2 focus-within:ring-indigo-500/50 focus-within:border-indigo-500 p-2 shadow-inner transition-all">

          <div className="p-2 text-slate-400">
            <Activity size={20} />
          </div>

          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage(e);
              }
            }}
            placeholder="Describe the patient's symptoms (e.g., 2 year old with fever and cough)..."
            className="flex-1 bg-transparent border-0 focus:ring-0 resize-none py-3 outline-none text-slate-800 placeholder:text-slate-400 max-h-32 min-h-12"
            rows={1}
            disabled={isLoading}
          />

          <button
            onClick={handleSendMessage}
            disabled={isLoading || !inputMessage.trim()}
            className="p-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm mb-1"
          >
            <Send size={18} />
          </button>
        </div>
        <div className="text-center mt-3 text-xs text-slate-400 font-medium pt-1">
          Medical Assistant 1.0 • For clinical decision support only
        </div>
      </footer>

    </div>
  );
}

export default App;
