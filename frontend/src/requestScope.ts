// A case change invalidates pending reads before they can publish into the new case.
// Refreshes within one scope share a request instead of starving slow responses.
export class RequestScope {
    private scope = '';
    private generation = 0;
    private pending: Promise<void> | null = null;
    private controller: AbortController | null = null;

    select(scope: string) {
        if (scope === this.scope) return;
        this.controller?.abort();
        this.scope = scope;
        this.generation++;
        this.pending = null;
    }

    matches(scope: string) { return this.scope === scope; }

    load<T>(scope: string, read: (signal: AbortSignal) => Promise<T>, publish: (value: T) => void,
            fail: (error: unknown) => void): Promise<void> {
        if (!this.matches(scope)) return Promise.resolve();
        if (this.pending) return this.pending;
        const generation = this.generation;
        const controller = new AbortController();
        this.controller = controller;
        const valid = () => this.generation === generation && !controller.signal.aborted;
        const pending = Promise.resolve().then(() => read(controller.signal)).then(value => {
            if (valid()) publish(value);
        }).catch(error => { if (valid()) fail(error); }).finally(() => {
            if (this.pending === pending) this.pending = null;
        });
        this.pending = pending;
        return pending;
    }
}
