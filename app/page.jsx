"use client";

import { useState } from "react";

export default function Home() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState(null);

  const sampleQueries = [
    "What is the water consumption of Infosys in 2024?",
    "Compare Scope 1 emissions between TCS and Infosys in 2024.",
    "What is the climate risk mitigation strategy of Tata Consultancy Services?",
    "Rank pharmaceutical companies by water consumption."
  ];

  const handleAsk = async (queryText) => {
    const activeQuery = queryText || question;
    if (!activeQuery.trim()) return;

    setLoading(true);
    setError("");
    setAnswer("");
    setCitations([]);
    setSuccess(null);

    if (queryText) {
      setQuestion(queryText);
    }

    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: activeQuery })
      });

      if (!response.ok) {
        throw new Error(`API returned status ${response.status}`);
      }

      const data = await response.json();
      setSuccess(data.success);
      if (data.success) {
        setAnswer(data.answer);
        setCitations(data.citations || []);
      } else {
        setAnswer(data.answer || "No details returned.");
        setError(data.error || "Processing failed.");
      }
    } catch (err) {
      setError(err.message || "A connection error occurred.");
      setAnswer("⚠️ Failed to reach the API server. If deployed on Vercel, please check your serverless logs.");
      setSuccess(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      maxWidth: "960px",
      margin: "0 auto",
      padding: "40px 20px",
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
      gap: "24px"
    }}>
      {/* Header Section */}
      <header style={{ textAlign: "center", marginBottom: "12px" }}>
        <div style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "8px",
          backgroundColor: "rgba(0, 230, 118, 0.1)",
          padding: "6px 14px",
          borderRadius: "30px",
          color: "#00E676",
          fontSize: "13px",
          fontWeight: "600",
          letterSpacing: "0.5px",
          marginBottom: "16px",
          border: "1px solid rgba(0, 230, 118, 0.2)"
        }}>
          🌱 SUSTALLY ESG INTELLIGENCE
        </div>
        <h1 style={{
          fontFamily: "'Outfit', sans-serif",
          fontSize: "42px",
          fontWeight: "700",
          margin: "0 0 10px 0",
          letterSpacing: "-0.5px",
          background: "linear-gradient(135deg, #00E676 0%, #00B0FF 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent"
        }}>
          Multi-Agent Sustainability Analyst
        </h1>
        <p style={{
          fontSize: "16px",
          color: "#9E9E9E",
          maxWidth: "600px",
          margin: "0 auto",
          lineHeight: "1.5"
        }}>
          Ask quantitative, comparative, or narrative ESG questions across corporate BRSR disclosures with automated RAG grounding.
        </p>
      </header>

      {/* Query Search Panel */}
      <section style={{
        backgroundColor: "#1E222B",
        border: "1px solid #2D3139",
        borderRadius: "16px",
        padding: "24px",
        boxShadow: "0 10px 30px rgba(0,0,0,0.3)"
      }}>
        <div style={{ display: "flex", gap: "12px", width: "100%", marginBottom: "16px" }}>
          <input
            type="text"
            placeholder="e.g. Compare Scope 1 emissions between TCS and Infosys in 2024..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !loading) handleAsk();
            }}
            disabled={loading}
            style={{
              flex: 1,
              backgroundColor: "#0E1117",
              border: "1px solid #333943",
              borderRadius: "10px",
              padding: "16px",
              fontSize: "15px",
              color: "#E0E0E0",
              outline: "none",
              transition: "border-color 0.2s"
            }}
          />
          <button
            onClick={() => handleAsk()}
            disabled={loading || !question.trim()}
            style={{
              backgroundColor: loading || !question.trim() ? "#2E3B33" : "#00E676",
              color: loading || !question.trim() ? "#757575" : "#000",
              border: "none",
              borderRadius: "10px",
              padding: "0 28px",
              fontSize: "15px",
              fontWeight: "600",
              cursor: loading || !question.trim() ? "not-allowed" : "pointer",
              transition: "background-color 0.2s"
            }}
          >
            {loading ? "Analyzing..." : "Ask Agent"}
          </button>
        </div>

        {/* Suggestion Pills */}
        <div>
          <p style={{ margin: "0 0 10px 0", fontSize: "13px", color: "#757575", fontWeight: "500" }}>
            Suggested Queries:
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            {sampleQueries.map((q, idx) => (
              <button
                key={idx}
                onClick={() => handleAsk(q)}
                disabled={loading}
                style={{
                  backgroundColor: "#0E1117",
                  border: "1px solid #2D3139",
                  borderRadius: "20px",
                  padding: "8px 14px",
                  fontSize: "13px",
                  color: "#B0BEC5",
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "background-color 0.2s, border-color 0.2s"
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "#00E676";
                  e.currentTarget.style.backgroundColor = "rgba(0, 230, 118, 0.05)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "#2D3139";
                  e.currentTarget.style.backgroundColor = "#0E1117";
                }}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Loading Indicator */}
      {loading && (
        <div style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "12px",
          padding: "40px 0"
        }}>
          <div style={{
            width: "36px",
            height: "36px",
            border: "3px solid rgba(0, 230, 118, 0.1)",
            borderTopColor: "#00E676",
            borderRadius: "50%",
            animation: "spin 1s linear infinite"
          }} />
          <p style={{ color: "#9E9E9E", fontSize: "14px", margin: 0 }}>
            Orchestrating agents and generating disclosure audit report...
          </p>
          <style dangerouslySetInnerHTML={{__html: `
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          `}} />
        </div>
      )}

      {/* Answer & Citations Area */}
      {(answer || error) && !loading && (
        <section style={{
          backgroundColor: "#1E222B",
          border: `1px solid ${success === false ? "#E53935" : "#2D3139"}`,
          borderRadius: "16px",
          padding: "32px",
          boxShadow: "0 10px 30px rgba(0,0,0,0.3)"
        }}>
          {success === false && (
            <div style={{
              backgroundColor: "rgba(229, 57, 53, 0.1)",
              border: "1px solid rgba(229, 57, 53, 0.2)",
              color: "#EF5350",
              padding: "12px 16px",
              borderRadius: "8px",
              fontSize: "14px",
              marginBottom: "20px"
            }}>
              <strong>⚠️ Pipeline Execution Exception:</strong> {error}
            </div>
          )}

          <h3 style={{
            fontFamily: "'Outfit', sans-serif",
            fontSize: "20px",
            margin: "0 0 16px 0",
            color: success === false ? "#EF5350" : "#00E676"
          }}>
            Analyst Report Answer
          </h3>

          <div style={{
            lineHeight: "1.7",
            color: "#E0E0E0",
            fontSize: "15px",
            whiteSpace: "pre-wrap",
            margin: "0 0 24px 0"
          }}>
            {answer}
          </div>

          {/* Citations & Evidence section */}
          {citations.length > 0 && (
            <div style={{
              borderTop: "1px solid #2D3139",
              paddingTop: "20px",
              marginTop: "20px"
            }}>
              <h4 style={{
                fontFamily: "'Outfit', sans-serif",
                fontSize: "14px",
                margin: "0 0 12px 0",
                color: "#9E9E9E",
                letterSpacing: "0.5px"
              }}>
                VERIFIED CITATIONS & GROUNDING SOURCES
              </h4>
              <ul style={{
                margin: 0,
                paddingLeft: "20px",
                display: "flex",
                flexDirection: "column",
                gap: "8px"
              }}>
                {citations.map((cite, index) => (
                  <li key={index} style={{ color: "#B0BEC5", fontSize: "14px" }}>
                    {cite}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {/* Footer */}
      <footer style={{
        marginTop: "auto",
        textAlign: "center",
        padding: "24px 0 12px 0",
        color: "#5C6B73",
        fontSize: "13px",
        borderTop: "1px solid #1E222B"
      }}>
        Sustally ESG Intelligence Platform © 2026. Local dashboards remain accessible through Streamlit.
      </footer>
    </div>
  );
}
