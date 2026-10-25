<?php

namespace Tests\Feature;

use Illuminate\Http\Client\Request;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class PythonApiControllerTest extends TestCase
{
    private function getTargetBase(): string
    {
        $baseUrl = rtrim((string) config('services.python_monitoring.url', 'http://127.0.0.1:5001'), '/');
        $host = parse_url($baseUrl, PHP_URL_HOST) ?: '127.0.0.1';
        $port = parse_url($baseUrl, PHP_URL_PORT);
        return $port ? "{$host}:{$port}" : $host;
    }

    public function test_forwards_json_requests_and_preserves_the_python_response(): void
    {
        $target = $this->getTargetBase();
        Http::fake([
            $target.'/*' => Http::response(['devices' => []], 201),
        ]);

        $response = $this->postJson('/api/devices?source=dashboard', ['devices' => []]);

        $response->assertCreated()->assertJson(['devices' => []]);

        Http::assertSent(fn (Request $request): bool => $request->method() === 'POST'
            && str_contains($request->url(), $target.'/api/devices?source=dashboard')
            && $request['devices'] === []
        );
    }

    public function test_forwards_reclassify_request(): void
    {
        $target = $this->getTargetBase();
        Http::fake([
            $target.'/*' => Http::response(['ok' => true, 'reclassified' => []], 200),
        ]);

        $response = $this->postJson('/api/devices/reclassify');

        $response->assertOk()->assertJson(['ok' => true, 'reclassified' => []]);

        Http::assertSent(fn (Request $request): bool => $request->method() === 'POST'
            && str_contains($request->url(), $target.'/api/devices/reclassify')
        );
    }
}
