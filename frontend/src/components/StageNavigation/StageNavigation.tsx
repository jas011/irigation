import React, { useMemo, useState, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Check, ChevronLeft, ChevronRight } from "lucide-react";
import { useFieldContext } from "../../layouts/DashboardLayout";
import {
  ANALYSIS_STAGES,
  getStageByPath,
  getStageIndex,
} from "../../constants/analysisStages";
import type { AnalysisStageId } from "../../constants/analysisStages";
import {
  hasCachedCropResult,
  hasCachedMoistureResult,
} from "../../utils/analysisCache";
import "./StageNavigation.css";

interface StageNavigationProps {
  currentStage?: AnalysisStageId;
  variant?: "default" | "history";
  onNavigate?: (
    direction: "prev" | "next" | "jump",
    targetPath: string
  ) => void;
}

export const canAccessAnalysisStage = (
  stageId: AnalysisStageId,
  activeFieldId: string | null
): boolean => {
  if (!activeFieldId) return stageId === "area";

  if (stageId === "area" || stageId === "crop") {
    return true;
  }

  if (stageId === "moisture") {
    return hasCachedCropResult(activeFieldId);
  }

  return false;
};

const StageNavigation: React.FC<StageNavigationProps> = ({
  currentStage,
  variant = "default",
  onNavigate,
}) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { activeFieldId } = useFieldContext();

  const [isTransitioning, setIsTransitioning] = useState(false);
  const [rippleStage, setRippleStage] =
    useState<AnalysisStageId | null>(null);

  /*
   * Resolve current stage from:
   * 1. Explicit currentStage prop
   * 2. Current URL
   * 3. First stage when coming from history
   */
  const resolvedStage = useMemo(() => {
    if (currentStage) {
      return ANALYSIS_STAGES.find(
        (stage) => stage.id === currentStage
      );
    }

    const fromPath = getStageByPath(location.pathname);

    if (fromPath) {
      return fromPath;
    }

    if (variant === "history") {
      return ANALYSIS_STAGES[0];
    }

    return undefined;
  }, [currentStage, location.pathname, variant]);

  const currentIndex = resolvedStage
    ? getStageIndex(resolvedStage.id)
    : -1;

  const prevStage = currentIndex > 0 ? ANALYSIS_STAGES[currentIndex - 1] : null;
  const nextStage = currentIndex >= 0 && currentIndex < ANALYSIS_STAGES.length - 1 ? ANALYSIS_STAGES[currentIndex + 1] : null;
  const canAccessNext = nextStage ? canAccessAnalysisStage(nextStage.id, activeFieldId) : false;

  /*
   * Stage status
   */
  const getStageStatus = (
    index: number
  ): "completed" | "active" | "upcoming" => {
    if (index < currentIndex) return "completed";
    if (index === currentIndex) return "active";
    return "upcoming";
  };

  /*
   * Progress line
   */
  const trackFillPercent =
    currentIndex >= 0 && ANALYSIS_STAGES.length > 1
      ? (currentIndex / (ANALYSIS_STAGES.length - 1)) * 100
      : 0;

  /*
   * Navigation handler
   */
  const handleNavigate = useCallback(
    (
      direction: "prev" | "next" | "jump",
      targetPath: string,
      stageId?: AnalysisStageId
    ) => {
      if (isTransitioning) return;

      if (stageId) {
        setRippleStage(stageId);

        window.setTimeout(() => {
          setRippleStage(null);
        }, 600);
      }

      setIsTransitioning(true);

      sessionStorage.setItem(
        "agrisense_stage_direction",
        direction === "prev" ? "back" : "forward"
      );

      if (variant === "history") {
        sessionStorage.setItem("agrisense_from_history", "true");
      }

      window.setTimeout(() => {
        if (onNavigate) {
          onNavigate(direction, targetPath);
        } else {
          navigate(targetPath);
        }

        setIsTransitioning(false);
      }, 280);
    },
    [isTransitioning, navigate, onNavigate, variant]
  );

  /*
   * If stage cannot be resolved, don't render navigation.
   */
  if (!resolvedStage) {
    return null;
  }

  return (
    <nav
      className={`stage-nav ${
        variant === "history" ? "stage-nav--history" : ""
      } ${isTransitioning ? "stage-nav--transitioning" : ""}`}
      aria-label="Analysis stage navigation"
    >
      <div className="stage-nav-inner">
        {/* Left: Previous Button */}
        <button
          type="button"
          className="stage-nav-arrow-btn stage-nav-prev-btn"
          disabled={!prevStage || isTransitioning}
          onClick={() => {
            if (prevStage) {
              handleNavigate("prev", prevStage.path, prevStage.id);
            }
          }}
          title={prevStage ? `Previous: ${prevStage.label}` : "No previous stage"}
          aria-label="Previous Stage"
        >
          <ChevronLeft size={16} strokeWidth={2.5} />
          <span>Previous</span>
        </button>

        {/* Center: 1 — 2 — 3 */}
        <div className="stage-nav-progress">
          <div className="stage-nav-steps">
            {/* Progress line */}
            <div
              className="stage-nav-track"
              aria-hidden="true"
            >
              <div
                className="stage-nav-track-fill"
                style={{
                  width: `${trackFillPercent}%`,
                }}
              />
            </div>

            {/* ONLY 1 / 2 / 3 */}
            {ANALYSIS_STAGES.map((stage, index) => {
              const status = getStageStatus(index);

              const accessible = canAccessAnalysisStage(
                stage.id,
                activeFieldId
              );

              const isActive = status === "active";

              const hasResult =
                stage.id === "crop"
                  ? Boolean(
                      activeFieldId &&
                        hasCachedCropResult(activeFieldId)
                    )
                  : stage.id === "moisture"
                  ? Boolean(
                      activeFieldId &&
                        hasCachedMoistureResult(activeFieldId)
                    )
                  : false;

              return (
                <button
                  key={stage.id}
                  type="button"
                  className={`
                    stage-nav-step
                    stage-nav-step--${status}
                    ${
                      rippleStage === stage.id
                        ? "stage-nav-step--ripple"
                        : ""
                    }
                  `}
                  disabled={
                    !accessible ||
                    isActive ||
                    isTransitioning
                  }
                  onClick={() =>
                    handleNavigate(
                      "jump",
                      stage.path,
                      stage.id
                    )
                  }
                  title={stage.label}
                  aria-label={`Stage ${index + 1}: ${stage.label}`}
                  aria-current={
                    isActive ? "step" : undefined
                  }
                >
                  <span className="stage-nav-step-dot">
                    {status === "completed" ? (
                      <Check
                        size={16}
                        strokeWidth={3}
                      />
                    ) : (
                      index + 1
                    )}

                    {hasResult &&
                      status !== "active" && (
                        <span
                          className="stage-nav-step-result-dot"
                          aria-hidden="true"
                        />
                      )}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Right: Next Button */}
        <button
          type="button"
          className="stage-nav-arrow-btn stage-nav-next-btn"
          disabled={!nextStage || !canAccessNext || isTransitioning}
          onClick={() => {
            if (nextStage && canAccessNext) {
              handleNavigate("next", nextStage.path, nextStage.id);
            }
          }}
          title={
            !nextStage
              ? "At final stage"
              : !canAccessNext
              ? "Complete current stage first"
              : `Next: ${nextStage.label}`
          }
          aria-label="Next Stage"
        >
          <span>Next</span>
          <ChevronRight size={16} strokeWidth={2.5} />
        </button>
      </div>
    </nav>
  );
};

export default StageNavigation;