import { useApp } from "../context/AppContext";

export default function LoadingOverlay() {
  const { loading, loadingText } = useApp();
  if (!loading) return null;
  return (
    <div className="fixed inset-0 bg-[#f8faf9]/80 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="text-center">
        <div
          className="w-8 h-8 border-2 rounded-full animate-spin mx-auto mb-4"
          style={{
            borderColor: "rgba(67, 101, 101, 0.2)",
            borderTopColor: "var(--primary)",
          }}
        />
        <p className="text-sm text-[#596060]">
          {loadingText || "Processing..."}
        </p>
      </div>
    </div>
  );
}
