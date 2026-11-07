import React, { useState, useEffect } from 'react';
import {
  Mic,
  RotateCcw,
  Sparkles,
  Filter,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Clock,
  Layers,
  RefreshCw,
} from 'lucide-react';
import PageHeader from '../common/PageHeader';
import LoadingState from '../common/LoadingState';
import ErrorBox from '../common/ErrorBox';
import InterviewProgress from './InterviewProgress';
import InterviewQuestionCard from './InterviewQuestionCard';
import { echoApi } from '../../api';

export default function ExitInterview({ onAnswerSubmitted, focusArtifactId, activeProject, refreshKey }) {
  const [data, setData] = useState(null);
  const [answers, setAnswers] = useState({});
  const [saved, setSaved] = useState({});
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState(null);
  const [err, setErr] = useState(null);
  const [secondsLeft, setSecondsLeft] = useState(15 * 60);
  const [categoryFilter, setCategoryFilter] = useState('all');

  const loadQuestionsAndAnswers = async () => {
    setLoading(true);
    setErr(null);
    try {
      const pId = activeProject?.id;
      const [qData, aData] = await Promise.all([
        echoApi.getInterviewQuestions(6, pId),
        echoApi.getInterviewAnswers(pId).catch(() => ({ answers: [] })),
      ]);
      setData(qData);
      if (qData?.time_budget_minutes) {
        setSecondsLeft(qData.time_budget_minutes * 60);
      }
      if (aData && aData.answers) {
        const savedMap = {};
        const answersMap = {};
        aData.answers.forEach((a) => {
          savedMap[a.question_id] = true;
          answersMap[a.question_id] = a.answer;
        });
        setSaved(savedMap);
        setAnswers(answersMap);
      }
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQuestionsAndAnswers();
  }, [activeProject?.id, refreshKey]);

  // Countdown timer
  useEffect(() => {
    if (!data) return;
    const interval = setInterval(() => {
      setSecondsLeft((s) => Math.max(0, s - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [data]);

  // If focusArtifactId was passed from Risk Map, scroll into view
  useEffect(() => {
    if (focusArtifactId && data) {
      setTimeout(() => {
        const el = document.getElementById(`question-${focusArtifactId}`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          el.classList.add('ring-2', 'ring-purple-500');
          setTimeout(() => el.classList.remove('ring-2', 'ring-purple-500'), 2500);
        }
      }, 200);
    }
  }, [focusArtifactId, data]);

  const handleSubmitAnswer = async (q, answerText) => {
    setSavingId(q.id);
    try {
      await echoApi.submitInterviewAnswer({
        question_id: q.id,
        artifact_id: q.artifact_id,
        answer: answerText,
        submitted_by: data?.leaver?.name,
      });
      setSaved((prev) => ({ ...prev, [q.id]: true }));
      setAnswers((prev) => ({ ...prev, [q.id]: answerText }));
      if (onAnswerSubmitted) onAnswerSubmitted();
    } catch (e) {
      alert(`Failed to save answer: ${e.message}`);
    } finally {
      setSavingId(null);
    }
  };

  if (loading && !data) {
    return <LoadingState label="Generating grounded exit interview questions from git activity..." />;
  }

  if (err && !data) {
    return (
      <ErrorBox
        msg={err}
        hint="Ensure backend is running: uvicorn main:app --reload --port 8000"
        onRetry={loadQuestionsAndAnswers}
      />
    );
  }

  const answeredCount = Object.keys(saved).filter((k) => saved[k]).length;
  const totalQuestions = data?.questions?.length || 0;
  const leaverName = data?.leaver?.name || 'Departing Lead';

  // Filter questions
  const filteredQuestions = (data?.questions || []).filter((q) => {
    if (categoryFilter === 'all') return true;
    return q.gap_type === categoryFilter;
  });

  return (
    <div className="space-y-6 fade-in">
      {/* Page Header */}
      <PageHeader
        title="Exit Interview Extraction"
        subtitle={`Intelligent knowledge capture session with ${leaverName} (${data?.leaver?.role || 'Lead Engineer'})`}
        badge="Evidence Grounded"
        actions={
          <button
            onClick={loadQuestionsAndAnswers}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition shadow-xs"
          >
            <RefreshCw className="w-3.5 h-3.5 text-slate-400" />
            <span>Reload Questions</span>
          </button>
        }
      />

      {/* Progress & Timer Bar */}
      <InterviewProgress
        totalQuestions={totalQuestions}
        answeredCount={answeredCount}
        secondsLeft={secondsLeft}
        decisionCount={answeredCount}
      />

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 pb-3">
        <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0">
          {[
            { id: 'all', label: 'All Questions' },
            { id: 'undocumented_single_owner', label: 'Undocumented Modules' },
            { id: 'unexplained_change', label: 'Unexplained Changes' },
            { id: 'solo_external_contact', label: 'External Contacts' },
            { id: 'quiet_failure', label: 'Quiet Failures' },
          ].map((cat) => (
            <button
              key={cat.id}
              onClick={() => setCategoryFilter(cat.id)}
              className={`text-xs px-2.5 py-1 rounded-md font-medium transition shrink-0 ${
                categoryFilter === cat.id
                  ? 'bg-purple-50 text-purple-700 border border-purple-200'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50 border border-transparent'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        <span className="text-xs text-slate-400">
          Showing {filteredQuestions.length} of {totalQuestions} prioritized prompts
        </span>
      </div>

      {/* Questions List */}
      <div className="space-y-4">
        {filteredQuestions.length === 0 ? (
          <div className="p-8 text-center bg-white rounded-xl border border-dashed border-slate-200 text-slate-400 text-xs">
            No questions generated for this filter category.
          </div>
        ) : (
          filteredQuestions.map((q, idx) => (
            <InterviewQuestionCard
              key={q.id}
              question={q}
              index={idx}
              savedAnswer={answers[q.id]}
              isSaved={Boolean(saved[q.id])}
              onSaveAnswer={handleSubmitAnswer}
              saving={savingId === q.id}
            />
          ))
        )}
      </div>
    </div>
  );
}
