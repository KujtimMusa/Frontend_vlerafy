'use client';

import { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/stores/authStore';
import { showToast } from '@/lib/toast';

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setUser, setShopId } = useAuthStore();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    const shopId = searchParams.get('shop_id');
    const shop = searchParams.get('shop');
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
      if (shop) {
        localStorage.setItem('shop_domain', shop);
      }
    }

    setUser({ id: parseInt(shopId), name: 'Shop', email: null });
    setShopId(shopId);

    setStatus('success');
    showToast('Erfolgreich verbunden!');
    setTimeout(() => router.replace('/dashboard'), 1200);
  }, [searchParams, router, setUser, setShopId]);

  return (
    <div className="vlerafy-auth-page">
      <div className="vlerafy-auth-card">
        <div style={{ marginBottom: 20 }}>
          {status === 'loading' && (
            <div
              style={{
                width: 40,
                height: 40,
                border: '3px solid var(--v-gray-200)',
                borderTopColor: 'var(--v-navy-700)',
                borderRadius: '50%',
                animation: 'spin 0.8s linear infinite',
              }}
            />
          )}
          {status === 'success' && (
            <div
              style={{
                width: 64,
                height: 64,
                margin: '0 auto',
                borderRadius: '50%',
                background: 'var(--v-success-bg)',
                color: 'var(--v-success)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 32,
              }}
            >
              ✓
            </div>
          )}
          {status === 'error' && (
            <div
              style={{
                width: 64,
                height: 64,
                margin: '0 auto',
                borderRadius: '50%',
                background: 'var(--v-critical-bg)',
                color: 'var(--v-critical)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 32,
              }}
            >
              ✗
            </div>
          )}
        </div>
        <h2 className="vlerafy-auth-title">
          {status === 'loading' && 'Verbinde Shop...'}
          {status === 'success' && 'Erfolgreich verbunden!'}
          {status === 'error' && 'Fehler'}
        </h2>
        <p className="vlerafy-auth-subtitle">
          {errorMessage || (status === 'loading' ? 'Bitte warten' : 'Weiterleitung...')}
        </p>
      </div>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="vlerafy-auth-page">
          <div className="vlerafy-auth-card">
            <div style={{ marginBottom: 20 }}>
              <div
                style={{
                  width: 40,
                  height: 40,
                  border: '3px solid var(--v-gray-200)',
                  borderTopColor: 'var(--v-navy-700)',
                  borderRadius: '50%',
                  animation: 'spin 0.8s linear infinite',
                  margin: '0 auto',
                }}
              />
            </div>
            <h2 className="vlerafy-auth-title">Verbinde Shop...</h2>
            <p className="vlerafy-auth-subtitle">Bitte warten</p>
          </div>
        </div>
      }
    >
      <CallbackContent />
    </Suspense>
  );
}
