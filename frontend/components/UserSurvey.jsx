import React, { useState } from 'react';
import axios from 'axios';

const UserSurvey = ({ sessionId, userId, onSurveyComplete }) => {
  const [surveyData, setSurveyData] = useState({
    satisfaction: 3, // 1-5 scale
    easeOfUse: 3,    // 1-5 scale
    wouldRecommend: true,
    preferredFeatures: [],
    feedback: ''
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    
    if (type === 'checkbox') {
      const updatedFeatures = [...surveyData.preferredFeatures];
      if (checked) {
        updatedFeatures.push(value);
      } else {
        const index = updatedFeatures.indexOf(value);
        if (index !== -1) updatedFeatures.splice(index, 1);
      }
      setSurveyData(prev => ({ ...prev, preferredFeatures: updatedFeatures }));
    } else {
      setSurveyData(prev => ({ 
        ...prev, 
        [name]: type === 'number' ? parseInt(value, 10) : value 
      }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    
    try {
      const response = await axios.post('/api/survey', {
        sessionId,
        userId,
        surveyData: {
          ...surveyData,
          timestamp: new Date().toISOString()
        }
      });
      
      if (response.data.success) {
        setSuccess(true);
        if (onSurveyComplete) {
          onSurveyComplete(surveyData);
        }
      } else {
        setError('Failed to submit survey');
      }
    } catch (err) {
      setError('Error submitting survey: ' + (err.message || 'Unknown error'));
    } finally {
      setSubmitting(false);
    }
  };

  if (success) {
    return (
      <div className="survey-complete">
        <h3>Thank you for your feedback!</h3>
        <p>Your responses help us improve your experience.</p>
      </div>
    );
  }

  return (
    <div className="user-survey">
      <h2>Help Us Improve</h2>
      <p>Please take a moment to share your experience with Nom.</p>
      
      {error && <div className="error">{error}</div>}
      
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>
            How satisfied are you with your conversation? (1-5)
            <input 
              type="range" 
              name="satisfaction" 
              min="1" 
              max="5" 
              value={surveyData.satisfaction} 
              onChange={handleChange} 
            />
            <span>{surveyData.satisfaction}</span>
          </label>
        </div>
        
        <div className="form-group">
          <label>
            How easy was it to use Nom? (1-5)
            <input 
              type="range" 
              name="easeOfUse" 
              min="1" 
              max="5" 
              value={surveyData.easeOfUse} 
              onChange={handleChange} 
            />
            <span>{surveyData.easeOfUse}</span>
          </label>
        </div>
        
        <div className="form-group">
          <label>
            Would you recommend Nom to others?
            <input 
              type="checkbox" 
              name="wouldRecommend" 
              checked={surveyData.wouldRecommend} 
              onChange={(e) => setSurveyData(prev => ({ 
                ...prev, 
                wouldRecommend: e.target.checked 
              }))} 
            />
          </label>
        </div>
        
        <div className="form-group">
          <p>Which features did you prefer? (Check all that apply)</p>
          <label>
            <input 
              type="checkbox" 
              name="preferredFeatures" 
              value="conversation" 
              checked={surveyData.preferredFeatures.includes('conversation')} 
              onChange={handleChange} 
            />
            Conversation
          </label>
          <label>
            <input 
              type="checkbox" 
              name="preferredFeatures" 
              value="memory" 
              checked={surveyData.preferredFeatures.includes('memory')} 
              onChange={handleChange} 
            />
            Memory/Recognition
          </label>
          <label>
            <input 
              type="checkbox" 
              name="preferredFeatures" 
              value="assistance" 
              checked={surveyData.preferredFeatures.includes('assistance')} 
              onChange={handleChange} 
            />
            Assistance
          </label>
        </div>
        
        <div className="form-group">
          <label>
            Additional Feedback:
            <textarea 
              name="feedback" 
              value={surveyData.feedback} 
              onChange={handleChange} 
              rows="4"
            />
          </label>
        </div>
        
        <button type="submit" disabled={submitting}>
          {submitting ? 'Submitting...' : 'Submit Feedback'}
        </button>
      </form>
    </div>
  );
};

export default UserSurvey; 