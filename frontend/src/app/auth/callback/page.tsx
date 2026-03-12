'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { Loader2, CheckCircle, XCircle } from 'lucide-react';
import { showToast } from '@/lib/toast';

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setUser, setShopId } = useAuthStore();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    const shopId = searchParams.get('shop_id');
    const error = searchParams.get('error');

    if (error) {
      setStatus('error');
      setErrorMessage(error);
      showToast(`Auth fehlgeschlagen: ${error}`, { isError: true });
      setTimeout(() => router.push('/dashboard'), 3000);
      return;
    }

    if (!shopId) {
      setStatus('error');
      setErrorMessage('Keine Shop-ID erhalten');
      setTimeout(() => router.push('/dashboard'), 3000);
      return;
    }

    if (typeof window !== 'undefined') {
      localStorage.setItem('shop_id', shopId);
      localStorage.setItem('current_shop_id', shopId);
    }

    setUser({ id: parseInt(shopId), name: 'Shop', email: null });
    setShopId(shopId);

    setStatus('success');
    showToast('Erfolgreich verbunden!');
    setTimeout(() => router.replace('/dashboard'), 1200);
  }, [searchParams, router, setUser, setShopId]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 px-4">
      <div className="w-full max-w-md border border-slate-700 rounded-lg bg-slate-900/50 p-6 text-center">
        <div className="flex justify-center mb-4">
          {status === 'loading' && <Loader2 className="w-16 h-16 text-blue-500 animate-spin" />}
          {status === 'success' && <CheckCircle className="w-16 h-16 text-green-500" />}
          {status === 'error' && <XCircle className="w-16 h-16 text-red-500" />}
        </div>
        <h2 className="text-xl font-semibold mb-2">
          {status === 'loading' && 'Verbinde...'}
          {status === 'success' && 'Erfolgreich!'}
          {status === 'error' && 'Fehler'}
        </h2>
        <p className="text-slate-400">{errorMessage || 'Weiterleitung...'}</p>
      </div>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex justify-center items-center"><Loader2 className="w-8 h-8 animate-spin" /></div>}>
      <CallbackContent />
    </Suspense>
  );
}
