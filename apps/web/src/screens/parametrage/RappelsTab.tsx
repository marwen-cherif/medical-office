/**
 * Onglet « Rappels » du Paramétrage.
 *
 * Permet de configurer :
 *   - Activation des notifications Windows 11
 *   - Intervalle de la tâche planifiée (minutes)
 *
 * Affiche l'état courant de la tâche planifiée Windows et permet sa réinstallation.
 */
import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { Bell, CheckCircle2, Loader2, RefreshCw, Save, XCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { humanizeError } from '@/lib/errors';
import {
  useRappelsSettings,
  useSetRappelsSettings,
  useInstallRappelsTask,
  useTestRappelsNotification,
} from '@/hooks/rappels';

export function RappelsTab() {
  const settings = useRappelsSettings();
  const saveSettings = useSetRappelsSettings();
  const installTask = useInstallRappelsTask();
  const testNotification = useTestRappelsNotification();

  const [notifsEnabled, setNotifsEnabled] = useState(true);
  const [schedulerInterval, setSchedulerInterval] = useState(15);

  useEffect(() => {
    if (!settings.data) return;
    setNotifsEnabled(settings.data.notifs_enabled);
    setSchedulerInterval(settings.data.scheduler_interval);
  }, [settings.data]);

  function onSave() {
    if (schedulerInterval < 1) {
      toast.error("L'intervalle doit être ≥ 1 minute.");
      return;
    }
    saveSettings.mutate(
      {
        notifs_enabled: notifsEnabled,
        scheduler_interval: schedulerInterval,
        // L'indicatif pays est géré dans l'onglet WhatsApp — on relit la valeur
        // courante depuis les settings pour ne pas l'écraser.
        default_country: settings.data?.default_country ?? '+216',
      },
      {
        onSuccess: () => toast.success('Réglages rappels enregistrés.'),
        onError: (e) => toast.error(humanizeError(e)),
      }
    );
  }

  function onInstallTask() {
    installTask.mutate(undefined, {
      onSuccess: () => toast.success('Tâche planifiée installée.'),
      onError: (e) => toast.error(humanizeError(e)),
    });
  }

  function onTestNotification() {
    testNotification.mutate(undefined, {
      onSuccess: () => toast.success('Notification de test envoyée.'),
      onError: (e) => toast.error(humanizeError(e)),
    });
  }

  const task = settings.data;
  const isLoading = settings.isLoading;

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {/* Paramètres */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="size-4" /> Rappels automatiques
          </CardTitle>
          <CardDescription>
            Service de fond qui vérifie les rappels échus et émet des notifications Windows.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {isLoading && <p className="text-sm text-muted">Chargement…</p>}
          {settings.isError && <p className="text-sm text-red">{humanizeError(settings.error)}</p>}

          {/* Notifications Windows */}
          <div className="flex items-center justify-between gap-4">
            <div>
              <Label htmlFor="rappels-notifs" className="text-sm font-medium">
                Notifications Windows 11
              </Label>
              <p className="text-xs text-muted mt-0.5">Toast natif à chaque rappel échu.</p>
            </div>
            <Switch
              id="rappels-notifs"
              checked={notifsEnabled}
              onCheckedChange={setNotifsEnabled}
            />
          </div>

          {/* Intervalle */}
          <div className="space-y-1.5">
            <Label htmlFor="rappels-interval">Intervalle de vérification (minutes)</Label>
            <Input
              id="rappels-interval"
              type="number"
              min={1}
              max={1440}
              value={schedulerInterval}
              onChange={(e) => setSchedulerInterval(Number(e.target.value))}
              className="w-28"
            />
            <p className="text-xs text-muted">
              La tâche planifiée Windows s'exécute toutes les N minutes.
            </p>
          </div>

          <Button onClick={onSave} disabled={saveSettings.isPending || isLoading}>
            {saveSettings.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Save className="size-4" />
            )}
            Enregistrer
          </Button>
        </CardContent>
      </Card>

      {/* Service de fond (worker tray) */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <RefreshCw className="size-4" /> Service de fond
          </CardTitle>
          <CardDescription>
            Le worker{' '}
            <code className="text-xs bg-bg px-1 py-0.5 rounded">crm-tray.exe</code>{' '}
            tourne en arrière-plan (icône dans la zone de notification) et émet les
            rappels même quand l'app est fermée.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isLoading && <p className="text-sm text-muted">Chargement…</p>}

          {task && (
            <div className="space-y-2.5 text-sm">
              {/* Présence */}
              <div className="flex items-center gap-2">
                {task.task_present ? (
                  <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />
                ) : (
                  <XCircle className="size-4 text-red shrink-0" />
                )}
                <span>{task.task_present ? 'Service installé' : 'Service absent'}</span>
              </div>

              {/* Activée */}
              {task.task_present && (
                <div className="flex items-center gap-2">
                  {task.task_enabled ? (
                    <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />
                  ) : (
                    <XCircle className="size-4 text-amber-500 shrink-0" />
                  )}
                  <span>{task.task_enabled ? 'Activé' : 'Désactivé'}</span>
                  {task.task_status && (
                    <span className="text-muted text-xs">({task.task_status})</span>
                  )}
                </div>
              )}

              {task.task_last_run && (
                <div className="text-muted text-xs">Dernière exécution : {task.task_last_run}</div>
              )}
              {task.task_next_run && (
                <div className="text-muted text-xs">Prochaine exécution : {task.task_next_run}</div>
              )}
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={onInstallTask}
              disabled={installTask.isPending || isLoading}
            >
              {installTask.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <RefreshCw className="size-4" />
              )}
              {task?.task_present ? 'Réinstaller le service' : 'Installer le service'}
            </Button>

            <Button
              variant="outline"
              onClick={onTestNotification}
              disabled={testNotification.isPending || isLoading}
            >
              {testNotification.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Bell className="size-4" />
              )}
              Tester la notification
            </Button>
          </div>

          <p className="text-xs text-muted">
            Le service se réinstalle aussi automatiquement au démarrage de l'application.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
