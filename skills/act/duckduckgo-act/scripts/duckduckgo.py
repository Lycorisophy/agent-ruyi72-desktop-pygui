#!/usr/bin/env python3
"""
DuckDuckGo Search Skill for Ruyi72
A professional web search using DuckDuckGo Instant Answers API
"""

import argparse
import json
import sys
from urllib.parse import quote_plus
import requests


def search_duckduckgo(query: str, num_results: int = 10, safe_search: str = "moderate") -> dict:
    """
    Perform a web search using DuckDuckGo Instant Answers API

    Args:
        query: Search query string
        num_results: Number of results to return (default: 10)
        safe_search: Safe search level - "strict", "moderate", or "off" (default: "moderate")

    Returns:
        Dictionary containing search results
    """
    try:
        # Map safe search values
        safe_map = {"strict": 1, "moderate": -1, "off": -2}
        kp_value = safe_map.get(safe_search, -1)

        # DuckDuckGo Instant Answers API
        encoded_query = quote_plus(query)
        api_url = (
            f"https://api.duckduckgo.com/"
            f"?q={encoded_query}"
            f"&format=json"
            f"&no_html=1"
            f"&skip_disambig=1"
            f"&kp={kp_value}"
        )

        headers = {
            'User-Agent': 'Ruyi72-DuckDuckGo/1.0',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        response = requests.get(api_url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        results = []
        suggestions = []

        # Helper function to extract results from RelatedTopics
        def extract_results(topics, max_items):
            count = 0
            for item in topics:
                if count >= max_items:
                    return count
                if isinstance(item, dict) and item.get('FirstURL'):
                    text = item.get('Text', '')
                    title = text.split(' - ')[0].strip() if ' - ' in text else text.split('<a')[0].strip()
                    if not title:
                        title = query
                    results.append({
                        'title': title,
                        'url': item.get('FirstURL', ''),
                        'snippet': text
                    })
                    count += 1
                # Check for nested Topics
                if isinstance(item, dict) and 'Topics' in item:
                    count += extract_results(item['Topics'], max_items - count)
                    if count >= max_items:
                        return count
            return count

        # Extract main results
        extract_results(data.get('RelatedTopics', []), num_results)

        # If no results from RelatedTopics, try Results field
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

        # Extract instant answer from Abstract
        instant_answer = None
        if data.get('Abstract'):
            instant_answer = {
                'title': data.get('Heading', query),
                'text': data.get('Abstract', ''),
                'source': data.get('AbstractSource', ''),
                'url': data.get('AbstractURL', '')
            }
        elif data.get('Answer'):
            instant_answer = {
                'title': data.get('Heading', query),
                'text': data.get('Answer', ''),
                'source': '',
                'url': ''
            }
        elif data.get('Definition'):
            instant_answer = {
                'title': f"Definition: {data.get('Heading', query)}",
                'text': data.get('Definition', ''),
                'source': data.get('DefinitionSource', ''),
                'url': data.get('DefinitionURL', '')
            }

        # Extract suggestions from redirection
        redirect = data.get('Redirect', '')

        return {
            'success': True,
            'query': query,
            'count': len(results),
            'results': results,
            'instant_answer': instant_answer,
            'suggestion': redirect,
            'meta': {
                'engine': 'DuckDuckGo',
                'safe_search': safe_search
            }
        }

    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': 'Search timeout - please try again',
            'query': query
        }
    except requests.exceptions.RequestException as e:
        return {
            'success': False,
            'error': f'Network error: {str(e)}',
            'query': query
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Search error: {str(e)}',
            'query': query
        }


def format_output(search_result: dict) -> str:
    """Format search results for display in Ruyi72"""
    if not search_result.get('success'):
        return f"[!] Search failed: {search_result.get('error', 'Unknown error')}"

    query = search_result.get('query', '')
    results = search_result.get('results', [])
    count = search_result.get('count', 0)
    instant = search_result.get('instant_answer')
    suggestion = search_result.get('suggestion')
    meta = search_result.get('meta', {})

    output_lines = []

    # Header
    output_lines.append("=" * 70)
    output_lines.append(f"🔍 DuckDuckGo Search: {query}")
    output_lines.append(f"Engine: {meta.get('engine', 'DuckDuckGo')} | Safe Search: {meta.get('safe_search', 'moderate')}")
    output_lines.append("=" * 70)

    # Instant Answer
    if instant:
        output_lines.append("\n📌 INSTANT ANSWER:")
        output_lines.append("-" * 40)
        output_lines.append(f"【{instant['title']}】")
        output_lines.append(instant['text'])
        if instant.get('source'):
            output_lines.append(f"\n  Source: {instant['source']}")

    # Suggestion
    if suggestion:
        output_lines.append(f"\n💡 Did you mean: {suggestion}")

    # Results
    if results:
        output_lines.append(f"\n📄 WEB RESULTS ({count} found):")
        output_lines.append("-" * 40)

        for i, result in enumerate(results, 1):
            title = result.get('title', 'No title')
            url = result.get('url', '')
            snippet = result.get('snippet', '')

            # Clean up snippet
            if ' - ' in snippet:
                snippet = snippet.split(' - ', 1)[1].strip()
            if '<a' in snippet:
                snippet = snippet.split('<a')[0].strip()

            output_lines.append(f"\n{i}. {title}")
            output_lines.append(f"   🔗 {url}")
            if snippet:
                if len(snippet) > 300:
                    snippet = snippet[:300] + "..."
                output_lines.append(f"   📝 {snippet}")
    else:
        output_lines.append("\n⚠️ No web results found.")

    output_lines.append("\n" + "=" * 70)

    return "\n".join(output_lines)


def main():
    parser = argparse.ArgumentParser(
        description='DuckDuckGo Search Tool for Ruyi72',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python duckduckgo.py "Python programming"
  python duckduckgo.py "Ruyi72 AI" --num 10
  python duckduckgo.py "definition:AI" --safe strict
        """
    )
    parser.add_argument('query', nargs='*', help='Search query')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--num', type=int, default=10, help='Number of results (default: 10)')
    parser.add_argument('--safe', choices=['strict', 'moderate', 'off'],
                        default='moderate', help='Safe search level')

    args = parser.parse_args()

    if not args.query:
        print("Error: Please provide a search query")
        print("Usage: python duckduckgo.py <search query>")
        sys.exit(1)

    query = ' '.join(args.query)
    result = search_duckduckgo(query, args.num, args.safe)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_output(result))


if __name__ == '__main__':
    main()
