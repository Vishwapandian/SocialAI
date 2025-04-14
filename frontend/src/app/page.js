"use client";

import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import ProtectedRoute from '../components/ProtectedRoute';

export default function Home() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hello! I\'m Neko the cat. Ask me anything! Meow~' }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const messagesEndRef = useRef(null);
  const { user, logout } = useAuth();
  const [hasInteracted, setHasInteracted] = useState(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Handle page load and unload events
  useEffect(() => {
    // Function to end chat session
    const endChat = async () => {
      if (sessionId && user?.uid && hasInteracted) {
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 1000);
          
          await fetch('http://localhost:5000/api/end-chat', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
              sessionId,
              userId: user.uid
            }),
            credentials: 'include',
            signal: controller.signal
          });
          
          clearTimeout(timeoutId);
        } catch (error) {
          console.error('Error ending chat session:', error);
        }
      }
    };

    // Add event listeners for page unload
    const handleBeforeUnload = (e) => {
      if (hasInteracted && messages.length > 1) {
        endChat();
        
        // This message is typically ignored by modern browsers,
        // but we include it for older browsers
        e.preventDefault();
        e.returnValue = '';
        return '';
      }
    };

    // Register event listeners
    window.addEventListener('beforeunload', handleBeforeUnload);
    
    // Clean up event listeners when component unmounts
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      endChat();
    };
  }, [sessionId, user, hasInteracted, messages.length]);

  const endChatSession = async () => {
    if (!sessionId || !user?.uid || !hasInteracted) return;
    
    try {
      await fetch('http://localhost:5000/api/end-chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          sessionId: sessionId,
          userId: user.uid
        }),
        credentials: 'include'
      });
    } catch (error) {
      console.error('Error ending chat session:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!input.trim()) return;
    
    // Mark as interacted once user sends a message
    setHasInteracted(true);
    
    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: input }]);
    setIsLoading(true);
    
    try {
      const response = await fetch('http://localhost:5000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          message: input,
          sessionId: sessionId,
          userId: user?.uid // Include user ID in the request
        }),
        credentials: 'include'
      });
      
      const data = await response.json();
      
      // Save the session ID
      if (data.sessionId) {
        setSessionId(data.sessionId);
      }
      
      // Add bot response
      setMessages(prev => [...prev, { role: 'assistant', content: data.response }]);
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: 'Meow~ I seem to be having trouble connecting. Try again later?' 
      }]);
    } finally {
      setIsLoading(false);
      setInput('');
    }
  };

  const handleLogout = async () => {
    try {
      // End chat session before logging out
      if (sessionId && user?.uid && hasInteracted) {
        await endChatSession();
      }
      
      await logout();
      // Clear chat history when logging out
      setSessionId(null);
      setMessages([
        { role: 'assistant', content: 'Hello! I\'m Neko the cat. Ask me anything! Meow~' }
      ]);
      setHasInteracted(false);
    } catch (error) {
      console.error('Failed to log out:', error);
    }
  };

  return (
    <ProtectedRoute>
      <main className="flex min-h-screen flex-col items-center justify-between p-4 md:p-24">
        <div className="z-10 w-full max-w-3xl">
          <div className="flex justify-between items-center mb-8">
            <h1 className="text-4xl font-bold text-center">Chat with Neko</h1>
            <button 
              onClick={handleLogout}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-white"
            >
              Sign Out
            </button>
          </div>
          
          <div className="bg-white/10 p-4 rounded-lg shadow-lg mb-4 h-[60vh] overflow-y-auto">
            {messages.map((message, i) => (
              <div 
                key={i} 
                className={`mb-4 ${
                  message.role === 'user' 
                    ? 'text-right' 
                    : 'text-left'
                }`}
              >
                <div 
                  className={`inline-block p-3 rounded-lg ${
                    message.role === 'user' 
                      ? 'bg-blue-500 text-white rounded-br-none' 
                      : 'bg-gray-300 text-black rounded-bl-none'
                  }`}
                >
                  {message.content}
                </div>
                <div className="text-xs mt-1 text-gray-400">
                  {message.role === 'user' ? user?.email || 'You' : 'Neko'}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="text-left mb-4">
                <div className="inline-block p-3 rounded-lg bg-gray-300 text-black rounded-bl-none">
                  <div className="flex space-x-2">
                    <div className="h-2 w-2 bg-gray-500 rounded-full animate-bounce"></div>
                    <div className="h-2 w-2 bg-gray-500 rounded-full animate-bounce delay-75"></div>
                    <div className="h-2 w-2 bg-gray-500 rounded-full animate-bounce delay-150"></div>
                  </div>
                </div>
                <div className="text-xs mt-1 text-gray-400">Neko</div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
          
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask Neko something..."
              className="flex-1 p-2 rounded-lg bg-white/10 border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isLoading}
            />
            <button 
              type="submit" 
              className="bg-blue-500 text-white px-4 py-2 rounded-lg disabled:opacity-50"
              disabled={isLoading || !input.trim()}
            >
              Send
            </button>
          </form>
        </div>
      </main>
    </ProtectedRoute>
  );
}
