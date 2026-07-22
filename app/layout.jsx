export const metadata = {
  title: "Sustally — AI Sustainability Intelligence",
  description: "Production-grade multi-agent ESG sustainability agent and dashboard.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="true" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body style={{ 
        margin: 0, 
        padding: 0, 
        backgroundColor: "#0E1117", 
        color: "#E0E0E0", 
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
        WebkitFontSmoothing: "antialiased"
      }}>
        {children}
      </body>
    </html>
  );
}
