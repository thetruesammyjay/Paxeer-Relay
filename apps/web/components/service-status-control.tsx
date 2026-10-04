"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ServiceRecord } from "@/hooks/use-services";
import { updateServiceStatus } from "@/hooks/use-services";
import { ApiError } from "@/lib/api-client";

type TargetStatus = "active" | "inactive";

function statusErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "The API key was not accepted. Reconnect and try again.";
    if (error.status === 403) return "This key needs services:write access to change routing.";
    if (error.status === 404) return "This service is no longer available in this project.";
    if (error.status === 409) return "A deprecated service cannot be paused or resumed.";
    return `The service status could not be changed (HTTP ${error.status}). Try again shortly.`;
  }
  return "The API could not be reached. Check the connection and try again.";
}

interface ServiceStatusControlProps {
  service: ServiceRecord;
  apiKey: string;
  connectionId: string;
}

export function ServiceStatusControl({
  service,
  apiKey,
  connectionId,
}: ServiceStatusControlProps) {
  const queryClient = useQueryClient();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [target, setTarget] = useState<TargetStatus | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const nextStatus: TargetStatus | null =
    service.status === "active"
      ? "inactive"
      : service.status === "inactive"
        ? "active"
        : null;

  const mutation = useMutation({
    mutationFn: (status: TargetStatus) =>
      updateServiceStatus(apiKey, service.id, status),
    onSuccess: (updated) => {
      queryClient.setQueryData<ServiceRecord[]>(
        ["services", connectionId],
        (records) =>
          records?.map((record) =>
            record.id === updated.id ? updated : record,
          ),
      );
      void queryClient.invalidateQueries({
        queryKey: ["services", connectionId],
      });
      setTarget(null);
    },
    onError: (error) => setErrorMessage(statusErrorMessage(error)),
  });

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (target && !dialog.open) dialog.showModal();
    if (!target && dialog.open) dialog.close();
  }, [target]);

  function beginChange() {
    if (!nextStatus || mutation.isPending) return;
    setErrorMessage("");
    setTarget(nextStatus);
  }

  function confirmChange() {
    if (!target || mutation.isPending) return;
    setErrorMessage("");
    mutation.mutate(target);
  }

  return (
    <>
      {nextStatus ? (
        <button
          className="button service-status-action"
          type="button"
          onClick={beginChange}
          disabled={mutation.isPending}
          aria-label={`${nextStatus === "inactive" ? "Pause" : "Resume"} ${service.name}`}
        >
          {mutation.isPending ? "Saving…" : nextStatus === "inactive" ? "Pause" : "Resume"}
        </button>
      ) : (
        <span className="service-status-terminal">No status action</span>
      )}
      {errorMessage && !target ? (
        <span className="service-status-error" role="alert">
          {errorMessage}
        </span>
      ) : null}
      <dialog
        ref={dialogRef}
        className="service-status-dialog"
        aria-labelledby={`service-status-title-${service.id}`}
        aria-describedby={`service-status-copy-${service.id}`}
        onCancel={(event) => {
          event.preventDefault();
          if (!mutation.isPending) setTarget(null);
        }}
        onClick={(event) => {
          if (event.target === event.currentTarget && !mutation.isPending) {
            setTarget(null);
          }
        }}
      >
        {target ? (
          <>
            <p className="eyebrow">Service routing</p>
            <h2 id={`service-status-title-${service.id}`}>
              {target === "inactive" ? "Pause this service?" : "Resume this service?"}
            </h2>
            <p
              id={`service-status-copy-${service.id}`}
              className="service-status-dialog-copy"
            >
              {target === "inactive"
                ? "New requests will stop being routed here. An unexpired quote already issued may still complete while the provider remains active and healthy. Pausing cannot reverse an external payment already sent."
                : "New requests can be routed here again when the provider is active and the service has a passing health probe."}
            </p>
            {errorMessage ? (
              <p className="service-status-error" role="alert">
                {errorMessage}
              </p>
            ) : null}
            <div className="service-status-dialog-actions">
              <button
                className="button"
                type="button"
                onClick={() => setTarget(null)}
                disabled={mutation.isPending}
              >
                Keep current status
              </button>
              <button
                className={`button ${target === "inactive" ? "danger" : "primary"}`}
                type="button"
                onClick={confirmChange}
                disabled={mutation.isPending}
              >
                {mutation.isPending
                  ? "Saving…"
                  : target === "inactive"
                    ? "Pause service"
                    : "Resume service"}
              </button>
            </div>
          </>
        ) : null}
      </dialog>
    </>
  );
}
