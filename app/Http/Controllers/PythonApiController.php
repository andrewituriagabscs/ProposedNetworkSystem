<?php

namespace App\Http\Controllers;

use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Symfony\Component\HttpFoundation\Response;

class PythonApiController extends Controller
{
    /**
     * Ensure the internal Python monitoring engine is running in the background.
     */
    private function ensurePythonRunning(): void
    {
        $fp = @fsockopen('127.0.0.1', 5000, $errno, $errstr, 0.2);
        if ($fp) {
            fclose($fp);
            return;
        }

        $baseDir = base_path();
        if (strtoupper(substr(PHP_OS, 0, 3)) === 'WIN') {
            pclose(popen("start /B python -u \"{$baseDir}\\app.py\"", "r"));
        } else {
            exec("python -u \"{$baseDir}/app.py\" > /dev/null 2>&1 &");
        }
        usleep(400000); // 400ms warmup
    }

    public function forward(Request $request, string $path): Response
    {
        $baseUrl = rtrim((string) config('services.python_monitoring.url', 'http://127.0.0.1:5000'), '/');
        $pendingRequest = Http::connectTimeout(3)
            ->timeout(180)
            ->accept($request->header('Accept', 'application/json'));

        if ($request->getContent() !== '') {
            $pendingRequest = $pendingRequest->withBody(
                $request->getContent(),
                $request->header('Content-Type', 'application/json')
            );
        }

        try {
            $upstream = $pendingRequest->send(
                $request->method(),
                $baseUrl.'/api/'.$path,
                ['query' => $request->query()]
            );
        } catch (ConnectionException) {
            // Attempt auto-start of internal Python engine if not active, then retry once
            $this->ensurePythonRunning();

            try {
                $upstream = $pendingRequest->send(
                    $request->method(),
                    $baseUrl.'/api/'.$path,
                    ['query' => $request->query()]
                );
            } catch (ConnectionException) {
                return response()->json([
                    'error' => 'Internal monitoring service is unavailable.',
                ], 503);
            }
        }

        $headers = [];
        foreach (['content-type', 'content-disposition', 'cache-control'] as $header) {
            $value = $upstream->header($header);
            if ($value !== null) {
                $headers[$header] = $value;
            }
        }

        return response($upstream->body(), $upstream->status(), $headers);
    }
}
