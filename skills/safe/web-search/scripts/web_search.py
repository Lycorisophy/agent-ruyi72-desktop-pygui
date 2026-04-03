#!/usr/bin/env python3
"""
Web Search Skill for OpenClaw
A simple web search using DuckDuckGo Instant Answers API
"""

import argparse
import json
import sys
from urllib.parse import quote_plus
import requests


def search_web(query: str, num_results: int = 5) -> dict:
    """
    Perform a web search using DuckDuckGo Instant Answers API

    Args:
        query: Search query string
        num_results: Number of results to return (default: 5)

    Returns:
        Dictionary containing search results
    """
    try:
        # Use DuckDuckGo Instant Answers API (JSON-based, reliable)
        encoded_query = quote_plus(query)
        api_url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1"

        headers = {
            'User-Agent': 'OpenClaw-WebSearch/1.0',
            'Accept': 'application/json',
        }

        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        results = []

        # Helper function to extract results from RelatedTopics
        def extract_results(topics):
            for item in topics:
                if len(results) >= num_results:
                    return
                if isinstance(item, dict) and item.get('FirstURL'):
                    # Clean up the result text (remove HTML anchor tags)
                    text = item.get('Text', '')
                    title = text.split(' - ')[0].strip() if ' - ' in text else text.split('<a')[0].strip()
                    if not title:
                        title = query
                    results.append({
                        'title': title,
                        'url': item.get('FirstURL', ''),
                        'snippet': text
                    })
                # Check for nested Topics
                if isinstance(item, dict) and 'Topics' in item:
                    extract_results(item['Topics'])

        extract_results(data.get('RelatedTopics', []))

        # If no results from RelatedTopics, try Results (direct results)
        if not results:
            for item in data.get('Results', []):
                if len(results) >= num_results:
                    break
                if isinstance(item, dict) and item.get('FirstURL'):
                    text = item.get('Result', '')
                    title = item.get('Heading', query)
                    results.append({
                        'title': title,
                        'url': item.get('FirstURL', ''),
                        'snippet': text
                    })

        # If still no results, try Abstract (Wikipedia-style info)
        if not results and data.get('Abstract'):
            results.append({
                'title': data.get('Heading', query),
                'url': data.get('AbstractURL', ''),
                'snippet': data.get('Abstract', '')
            })

        # If still no results, try Answer
        if not results and data.get('Answer'):
            results.append({
                'title': data.get('Heading', query),
                'url': '',
                'snippet': data.get('Answer', '')
            })

        return {
            'success': True,
            'query': query,
            'count': len(results),
            'results': results
        }

    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': f"Network error: {str(e)}",
            'query': query
        }
    except Exception as e:
        return {
            'success': False,
            'error': f"Search error: {str(e)}",
            'query': query
        }


def format_results(search_result: dict) -> str:
    """Format search results for display"""
    if not search_result.get('success'):
        return f"❌ Search failed: {search_result.get('error', 'Unknown error')}"

    query = search_result.get('query', '')
    results = search_result.get('results', [])
    count = search_result.get('count', 0)

    if not results:
        return f"🔍 No results found for: '{query}'"

    output = [f"🌐 Search Results for: '{query}'\n"]
    output.append(f"Found {count} results:\n")
    output.append("-" * 60 + "\n")

    for i, result in enumerate(results, 1):
        title = result.get('title', 'No title')
        url = result.get('url', '')
        snippet = result.get('snippet', '')

        output.append(f"{i}. {title}\n")
        output.append(f"   📎 {url}\n")
        if snippet:
            # Clean up snippet (remove URL if present)
            if ' - ' in snippet:
                snippet = snippet.split(' - ', 1)[1].strip()
            # Truncate long snippets
            if len(snippet) > 200:
                snippet = snippet[:200] + "..."
            output.append(f"   💡 {snippet}\n")
        output.append("\n")

    return "".join(output)


def main():
    parser = argparse.ArgumentParser(description='Web Search Tool')
    parser.add_argument('query', nargs='*', help='Search query')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--num', type=int, default=5, help='Number of results (default: 5)')

    args = parser.parse_args()

    if not args.query:
        print("Error: Please provide a search query")
        print("Usage: python web_search.py <search query>")
        sys.exit(1)

    query = ' '.join(args.query)
    result = search_web(query, args.num)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_results(result))


if __name__ == '__main__':
    main()
