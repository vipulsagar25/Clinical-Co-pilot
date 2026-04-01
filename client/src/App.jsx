import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import {
  Send,
  Stethoscope,
  User,
  Loader2,
  Trash2,
  Github,
  Activity,
  ChevronRight,
  ShieldPlus
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

const SUGGESTED_SCENARIOS = [
  "2 year old with fever and fast breathing",
  "6 month baby with severe diarrhea and lethargy",
  "Child has chest indrawing and stridor",
  "Infant not feeding well, looks pale"
];

function App() {
  const [messages, setMessages] = useState(() => {
    const saved = localStorage.getItem('clinical_chat_v4');
    return saved ? JSON.parse(saved) : [];
  });

  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
    localStorage.setItem('clinical_chat_v4', JSON.stringify(messages));
  }, [messages]);

  const handleSendMessage = async (e, customMessage = null) => {
    e?.preventDefault();
    const msgToProcess = customMessage || inputMessage;

    if (!msgToProcess.trim() || isLoading) return;

    const userMessage = {
      role: 'user',
      content: msgToProcess.trim(),
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/chat`, {
        message: userMessage.content,
        history: messages.map(m => ({ role: m.role, content: m.content }))
      });

      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: response.data.response,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } catch (error) {
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: "⚠️ **System Error**: Failed to fetch clinical protocol. Check connection.",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const parseClinicalResponse = (content) => {
    const sections = {};

    // Extract Emergency Alert (if exists)
    const emergencyMatch = content.match(/⚠️ DANGER SIGNS DETECTED: (.*) IMMEDIATE REFERRAL/);
    if (emergencyMatch) {
      sections.emergency = emergencyMatch[1];
    }

    // Split by known headers
    const headers = [
      'Assessment:',
      'Risk Level:',
      'Confidence:',
      'Recommended Action:',
      'Evidence:',
      'Key Questions to Ask:'
    ];

    let currentPos = 0;
    headers.forEach((header, idx) => {
      const startIdx = content.indexOf(header);
      if (startIdx !== -1) {
        // Find where the next header starts
        let nextHeaderIdx = -1;
        for (let j = idx + 1; j < headers.length; j++) {
          const pos = content.indexOf(headers[j]);
          if (pos !== -1 && (nextHeaderIdx === -1 || pos < nextHeaderIdx)) {
            nextHeaderIdx = pos;
          }
        }

        const sectionContent = nextHeaderIdx !== -1
          ? content.substring(startIdx + header.length, nextHeaderIdx).trim()
          : content.substring(startIdx + header.length).trim();

        sections[header.replace(':', '')] = sectionContent;
      }
    });

    return sections;
  };

  const formatContent = (content) => {
    if (content.startsWith('**System Error**')) {
      return <div className="text-red-500 font-medium">{content}</div>;
    }

    const sections = parseClinicalResponse(content);

    if (Object.keys(sections).length === 0) {
      return <div className="clinical-content whitespace-pre-wrap">{content}</div>;
    }

    return (
      <div className="space-y-4 py-1">
        {sections.emergency && (
          <div className="emergency-block animate-pulse-slow">
            <div className="flex items-center gap-2 mb-1">
              <Activity size={16} />
              <span>DANGER SIGNS DETECTED</span>
            </div>
            <p className="text-sm opacity-90">{sections.emergency}</p>
            <p className="text-[11px] mt-2 border-t border-red-200 pt-2 uppercase tracking-tight">Immediate Referral Required</p>
          </div>
        )}

        {sections.Assessment && (
          <div className="clinical-section">
            <div className="clinical-header"><Stethoscope size={14} /> Assessment</div>
            <div className="assessment-content">{sections.Assessment}</div>
          </div>
        )}

        <div className="flex flex-wrap gap-4 items-start">
          {sections['Risk Level'] && (
            <div className="clinical-section min-w-[140px]">
              <div className="clinical-header">Risk Level</div>
              <div className={`risk-level-pill ${sections['Risk Level'].toLowerCase().includes('high') ? 'risk-high' :
                  sections['Risk Level'].toLowerCase().includes('moderate') ? 'risk-moderate' : 'risk-low'
                }`}>
                {sections['Risk Level'].split('—')[0].trim()}
              </div>
            </div>
          )}

          {sections.Confidence && (
            <div className="clinical-section">
              <div className="clinical-header">Retrieval Confidence</div>
              <div className="flex items-center gap-3">
                <div className="confidence-bar-container">
                  <div className={`confidence-fill ${sections.Confidence.toLowerCase().includes('high') ? 'confidence-high' :
                      sections.Confidence.toLowerCase().includes('medium') ? 'confidence-medium' : 'confidence-low'
                    }`} />
                </div>
                <span className="text-[11px] font-bold text-slate-500 uppercase">{sections.Confidence.split('—')[0].trim()}</span>
              </div>
            </div>
          )}
        </div>

        {sections['Recommended Action'] && (
          <div className="clinical-section">
            <div className="clinical-header">Recommended Action</div>
            <div className="action-card">
              {sections['Recommended Action']}
            </div>
          </div>
        )}

        {sections.Evidence && (
          <div className="clinical-section border-t border-slate-100 pt-3">
            <div className="clinical-header">Evidence & Citations</div>
            <div className="space-y-2 mt-2">
              {sections.Evidence.split('\n').filter(l => l.trim()).map((line, i) => (
                <div key={i} className="evidence-quote">
                  {line.replace(/^- /, '')}
                </div>
              ))}
            </div>
          </div>
        )}

        {sections['Key Questions to Ask'] && (
          <div className="clinical-section bg-slate-50/50 p-3 rounded-xl border border-slate-100">
            <div className="clinical-header">Follow-up Questions</div>
            <div className="space-y-1 mt-1">
              {sections['Key Questions to Ask'].split('\n').filter(l => l.trim()).map((line, i) => (
                <div key={i} className="question-item">
                  <div className="question-bullet" />
                  <span className="text-sm">{line.replace(/^- /, '')}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col min-h-[100dvh] bg-[var(--background)]">

      {/* Navbar */}
      <header className="fixed top-0 left-0 right-0 bg-white py-2 md:py-3 px-4 md:px-6 flex items-center justify-between border-b border-slate-200 z-50 shadow-sm w-full">
        <div className="flex items-center gap-2 md:gap-3 min-w-0">
          <div className="w-8 h-8 md:w-10 md:h-10 shrink-0 bg-white border border-slate-200 rounded-lg md:rounded-xl flex items-center justify-center overflow-hidden shadow-sm">
            <img src="/logo1.png" alt="Clinical Co-pilot Logo" className="w-full h-full object-contain p-0.5 md:p-1" />
          </div>
          <div className="min-w-0 pr-2">
            <h1 className="text-[14px] md:text-[16px] font-bold text-slate-900 leading-tight truncate">Clinical Co-pilot</h1>
            <span className="text-[10px] md:text-[12px] font-medium text-blue-600 flex items-center gap-1 truncate">
              <span className="w-1.5 h-1.5 shrink-0 rounded-full bg-blue-500 animate-pulse"></span> IMCI Engine
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1 md:gap-2 shrink-0">
          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              title="Clear Chat"
              className="p-2 md:px-3 md:py-1.5 text-xs font-semibold text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors flex items-center gap-1.5"
            >
              <Trash2 className="w-4 h-4 md:w-3.5 md:h-3.5" /> <span className="hidden sm:inline">Clear</span>
            </button>
          )}
          <div className="hidden sm:block w-[1px] h-6 bg-slate-200 mx-1 md:mx-2"></div>
          <a
            href="https://github.com/vipulsagar25"
            target="_blank"
            rel="noopener noreferrer"
            title="Developer Hub"
            className="flex items-center gap-1.5 p-2 md:px-3 md:py-1.5 text-sm font-medium text-slate-600 bg-slate-50 hover:bg-slate-100 hover:text-slate-900 border border-slate-200 rounded-lg transition-all"
          >
            <Github className="w-4 h-4 md:w-4 md:h-4" /> <span className="hidden sm:inline">Developer Hub</span>
          </a>
        </div>
      </header>

      {/* Chat Body */}
      <main className="chat-area flex flex-col pt-[70px] md:pt-[80px] pb-[130px] w-full max-w-full relative">
        <div className="flex flex-col gap-2 max-w-5xl mx-auto w-full">

          {/* Welcome State */}
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 md:py-24 text-center animate-in fade-in duration-500">
              <div className="bg-blue-50 p-5 rounded-3xl mb-6 shadow-inner border border-blue-100">
                <Activity size={40} className="text-blue-600" />
              </div>
              <h2 className="text-2xl font-bold text-slate-800 tracking-tight">Clinical Decision Support</h2>
              <p className="text-sm text-slate-500 max-w-md mt-3 mx-auto leading-relaxed">
                An AI-driven assistant configured for the Integrated Management of Childhood Illnesses (IMCI).
              </p>

              <div className="w-full max-w-2xl mt-12 grid grid-cols-1 md:grid-cols-2 gap-3 text-left">
                {SUGGESTED_SCENARIOS.map((scenario, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(null, scenario)}
                    className="group bg-white border border-slate-200 p-4 rounded-xl hover:border-blue-300 hover:shadow-md transition-all active:scale-[0.98] text-left"
                  >
                    <div className="flex gap-3 justify-between items-center">
                      <p className="text-sm font-medium text-slate-700 group-hover:text-blue-700 line-clamp-2">"{scenario}"</p>
                      <ChevronRight size={16} className="text-slate-300 group-hover:text-blue-500 shrink-0" />
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex gap-3 animate-in fade-in slide-in-from-bottom-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
            >
              <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-2 ${msg.role === 'user' ? 'bg-blue-600 text-white shadow-sm' : 'bg-white border border-slate-200 shadow-sm text-blue-600'
                }`}>
                {msg.role === 'user' ? <User size={16} /> : <Stethoscope size={16} />}
              </div>

              <div className={`bubble ${msg.role === 'user' ? 'bubble-user' : 'bubble-bot'}`}>
                {formatContent(msg.content)}
                <span className="bubble-time">{msg.timestamp}</span>
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex gap-3 animate-in fade-in">
              <div className="w-8 h-8 rounded-full bg-white border border-slate-200 shadow-sm text-blue-600 flex items-center justify-center shrink-0 mt-2">
                <Stethoscope size={16} />
              </div>
              <div className="bubble bubble-bot animate-pulse max-w-[150px]">
                <div className="flex items-center gap-2 py-1">
                  <Loader2 size={16} className="animate-spin text-blue-500" />
                  <span className="text-slate-500 font-medium text-sm">Analyzing...</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} className="h-4" />
        </div>
      </main>

      {/* Input Bar */}
      <footer className="fixed bottom-0 left-0 right-0 bg-white px-4 md:px-8 py-4 border-t border-slate-200 shadow-[0_-4px_20px_-15px_rgba(0,0,0,0.1)] z-50">
        <div className="max-w-4xl mx-auto flex flex-col items-center">
          <form onSubmit={handleSendMessage} className="w-full relative flex items-end shadow-sm border border-slate-300 rounded-2xl bg-white overflow-hidden focus-within:ring-2 focus-within:ring-blue-100 focus-within:border-blue-400 transition-all">
            <textarea
              ref={inputRef}
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              placeholder="Detail patient symptoms and history..."
              className="w-full bg-transparent border-0 px-5 py-4 text-[15px] focus:ring-0 resize-none min-h-[56px] max-h-32 text-slate-800 placeholder:text-slate-400"
              rows={1}
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={!inputMessage.trim() || isLoading}
              className={`absolute right-2 bottom-2 p-2.5 rounded-xl transition-all flex items-center justify-center ${inputMessage.trim() ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-md' : 'bg-slate-100 text-slate-400'
                }`}
            >
              <Send size={18} />
            </button>
          </form>
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mt-3">
            Not a replacement for clinical judgment / Validation Required
          </span>
        </div>
      </footer>
    </div>
  );
}

export default App;
