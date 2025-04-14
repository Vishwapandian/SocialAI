# Neko Chat Application

A simple chat application with a Flask backend using Gemini API and a Next.js frontend.

## Setup

### Backend Setup

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the backend directory with your Gemini API key:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```

5. Start the Flask server:
   ```
   python server.py
   ```
   The server will run on http://localhost:5000

### Frontend Setup

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install the dependencies:
   ```
   npm install
   ```

3. Start the development server:
   ```
   npm run dev
   ```
   The frontend will run on http://localhost:3000

## Using the Chat Application

1. Open your browser and go to http://localhost:3000
2. Type your message in the input field and press Send
3. Neko the cat will respond to your message!

## Technologies Used

- Backend: Flask, Python
- Frontend: Next.js, React, Tailwind CSS
- API: Google Gemini AI 