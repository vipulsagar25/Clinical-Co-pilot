import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Send, Stethoscope, AlertTriangle, User, Bot, Loader2, Github } from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

// Example prompts for empty state
const EXAMPLE_PROMPTS = [
  { icon: '🔥', text: '2 year old with fever and cough', desc: 'respiratory infection' },
  { icon: '⚠️', text: '6 month baby with diarrhea', desc: 'diarrheal disease' },
  { icon: '📋', text: 'Child with severe malnutrition', desc: 'nutritional assessment' },
  { icon: '💊', text: 'Infant with inability to drink', desc: 'feeding difficulty' },
];

function App() {
  const [messages, setMessages] = useState(() => {
    const saved = localStorage.getItem('chat_messages');
    return saved ? JSON.parse(saved) : [];
  });

  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
    localStorage.setItem('chat_messages', JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSendMessage = async (e, customMessage = null) => {
    e.preventDefault();
    const messageText = customMessage || inputMessage.trim();
    
    if (!messageText) return;

    const userMessage = { role: 'user', content: messageText };
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/chat`, {
        message: messageText,
        history: messages.filter(m => m.role === 'user' || m.role === 'assistant')
      });

      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: response.data.response }
      ]);

    } catch (error) {
      console.error("Error connecting to backend:", error);
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: "⚠️ Error: Unable to connect to backend. Ensure the server is running on port 8000." }
      ]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const clearChat = () => {
    setMessages([]);
    localStorage.removeItem('chat_messages');
  };

  const handleExampleClick = (text) => {
    const event = new Event('submit', { bubbles: true });
    handleSendMessage(event, text);
  };

  return (
    <div className="flex flex-col h-screen w-full bg-gradient-to-b from-slate-50 to-slate-100">

      {/* Header */}
      <header className="bg-white border-b border-slate-200 shadow-sm sticky top-0 z-40">
        <div className="max-w-5xl mx-auto flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-blue-600 to-blue-700 text-white rounded-lg shadow-md flex-shrink-0">
              <Stethoscope size={24} />
            </div>
            <div>
              <h1 className="text-lg font-bold text-slate-900 leading-tight">Clinical Co-pilot</h1>
              <p className="text-xs text-slate-500 font-medium leading-tight">IMCI Guidelines Assistant</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <a
              href="https://github.com/vipulsagar25/"
              target="_blank"
              rel="noopener noreferrer"
              className="p-2.5 text-slate-600 hover:bg-slate-100 rounded-lg transition-colors flex-shrink-0" 
              title="Developer GitHub"
              aria-label="GitHub Profile"
            >
              <Github size={20} />
            </a>
            {messages.length > 0 && (
              <button
                onClick={clearChat}
                className="px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition-colors whitespace-nowrap"
                aria-label="Clear chat history"
              >
                Clear
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Chat Area */}
      <main className="flex-1 overflow-y-auto flex flex-col items-center w-full bg-gradient-to-b from-slate-50 via-slate-50 to-slate-100">
        <div className="w-full max-w-3xl px-4 py-8 md:py-12 flex flex-col flex-1">

          {/* Empty State */}
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center flex-1 py-16 md:py-20 text-center animate-in fade-in slide-in-from-bottom-4 duration-500">
              <div className="mb-10 md:mb-12">
                <div className="w-16 h-16 bg-gradient-to-br from-blue-100 to-blue-200 rounded-2xl flex items-center justify-center mx-auto mb-6 transform transition-transform duration-300 hover:scale-110">
                  <Stethoscope size={32} className="text-blue-600" />
                </div>
                <h2 className="text-2xl md:text-3xl font-bold text-slate-900 mb-3">Welcome to Clinical Co-pilot</h2>
                <p className="text-slate-600 max-w-md text-base">
                  Get IMCI-compliant clinical guidance for pediatric patient assessment. Describe symptoms to get started.
                </p>
              </div>

              {/* Example Prompts */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full mb-10 md:mb-12">
                {EXAMPLE_PROMPTS.map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleExampleClick(prompt.text)}
                    className="p-4 rounded-xl border border-slate-200 bg-white hover:bg-blue-50 hover:border-blue-300 hover:shadow-md transition-all duration-200 text-left group cursor-pointer prompt-enter"
                    style={{ animationDelay: `${idx * 75}ms` }}
                    aria-label={`Example: ${prompt.text}`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="text-2xl group-hover:scale-110 transform transition-transform duration-200">{prompt.icon}</span>
                      <div className="flex-1">
                        <p className="text-sm font-semibold text-slate-900 group-hover:text-blue-700">{prompt.text}</p>
                        <p className="text-xs text-slate-500 mt-1">{prompt.desc}</p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>

              <div className="text-xs text-slate-400 space-y-2">
                <p>💡 Start with a patient scenario for immediate guidance</p>
                <p>✓ Evidence-based recommendations from IMCI guidelines</p>
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.length > 0 && (
            <div className="space-y-6 md:space-y-8 w-full pb-6">
              {messages.map((msg, index) => {
                const isUser = msg.role === 'user';
                const isEmergency = typeof msg.content === 'string' && msg.content.includes('⚠️ DANGER SIGNS');

                return (
                  <div key={index} className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'} message-enter animate-in fade-in slide-in-from-bottom-2 duration-300 items-start`}>
                    {/* Avatar */}
                    {!isUser && (
                      <div className={`shrink-0 w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 transition-transform duration-300 ${
                        isEmergency ? 'bg-red-100 text-red-600 animate-pulse' : 'bg-blue-100 text-blue-600'
                      }`}
                      aria-label={isEmergency ? 'Critical alert' : 'Assistant message'}>
                        {isEmergency ? <AlertTriangle size={18} /> : <Bot size={18} />}
                      </div>
                    )}

                    {/* Message Bubble */}
                    <div className={`max-w-2xl rounded-xl p-4 md:p-5 transition-all duration-200 ${
                      isUser
                        ? 'bg-blue-600 text-white rounded-br-sm shadow-md hover:shadow-lg'
                        : isEmergency
                        ? 'bg-red-50 text-red-900 border border-red-200 rounded-bl-sm shadow-sm'
                        : 'bg-white text-slate-800 border border-slate-200 rounded-bl-sm shadow-sm hover:shadow-md'
                    }`}
                    role="article"
                    aria-label={`${isUser ? 'Your message' : 'Assistant message'}: ${msg.content.substring(0, 50)}`}>
                      {isEmergency && (
                        <div className="flex items-center gap-2 mb-3 font-bold text-red-700 text-xs pb-3 border-b border-red-200">
                          <AlertTriangle size={14} className="animate-pulse" />
                          CRITICAL ALERT
                        </div>
                      )}
                      <p className="text-sm md:text-base leading-relaxed whitespace-pre-wrap">
                        {msg.content}
                      </p>
                    </div>

                    {/* User Avatar */}
                    {isUser && (
                      <div className="shrink-0 w-9 h-9 rounded-lg bg-slate-300 text-slate-700 flex items-center justify-center flex-shrink-0 transition-transform duration-300 hover:scale-110"
                      aria-label="Your avatar">
                        <User size={18} />
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Loading State */}
              {isLoading && (
                <div className="flex gap-3 animate-in fade-in duration-300 mt-4 md:mt-6" role="status" aria-live="polite" aria-label="Loading response">
                  <div className="w-9 h-9 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center animate-pulse flex-shrink-0">
                    <Bot size={18} />
                  </div>
                  <div className="bg-white border border-slate-200 rounded-xl rounded-bl-sm p-4 md:p-5 shadow-sm">
                    <div className="flex items-center gap-2">
                      <Loader2 size={16} className="animate-spin text-blue-500" />
                      <span className="text-sm text-slate-500 font-medium">Analyzing guidelines...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </main>

      {/* Input Area */}
      <footer className="bg-gradient-to-t from-white via-white to-slate-50 border-t border-slate-200 sticky bottom-0 z-30 shadow-lg">
        <div className="flex justify-center w-full px-4 py-4 sm:py-5 md:py-6">
          <div className="w-full max-w-3xl">
            <form onSubmit={handleSendMessage} className="flex gap-3 items-end">
              <div className="flex-1 relative">
                <textarea
                  ref={inputRef}
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage(e);
                    }
                  }}
                  placeholder="Describe patient symptoms (e.g., 2-year-old with fever and cough)..."
                  className="w-full border border-slate-300 rounded-lg p-4 text-sm resize-none focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-400 focus:ring-opacity-50 focus:shadow-md transition-all bg-white placeholder:text-slate-400 min-h-12 max-h-32 leading-relaxed disabled:opacity-60 disabled:cursor-not-allowed"
                  rows={2}
                  disabled={isLoading}
                  style={{ lineHeight: '1.5rem' }}
                  maxLength={2000}
                  aria-label="Message input"
                  aria-describedby="char-count"
                />
                <div id="char-count" className="text-xs text-slate-400 mt-2 text-right">
                  {inputMessage.length}/2000
                </div>
              </div>
              <button
                type="submit"
                disabled={isLoading || !inputMessage.trim()}
                className="p-3.5 bg-gradient-to-br from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white rounded-lg disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg flex-shrink-0 h-12 w-12 flex items-center justify-center"
              >
                <Send size={20} />
              </button>
            </form>
            <div className="text-center mt-4 text-xs text-slate-500 font-medium">
              💡 Medical Assistant • For clinical decision support only
            </div>
          </div>
        </div>
      </footer>

    </div>
  );
}

export default App;
