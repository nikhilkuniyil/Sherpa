#!/usr/bin/env python3
"""
Configuration management for Sherpa.
Handles API keys and user preferences with secure local storage.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from getpass import getpass


def get_config_dir() -> Path:
    """Get the Sherpa config directory (~/.sherpa)"""
    config_dir = Path.home() / '.sherpa'
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the config file path"""
    return get_config_dir() / 'config.json'


def load_config() -> Dict[str, Any]:
    """Load configuration from file"""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to file"""
    config_path = get_config_path()
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    # Secure the file (read/write only for owner)
    config_path.chmod(0o600)


def get_api_key(prompt_if_missing: bool = True) -> Optional[str]:
    """
    Get an API key from any configured provider.

    Priority:
    1. Preferred provider from config
    2. Any available provider (Anthropic, OpenAI, Gemini)
    3. Interactive prompt (if prompt_if_missing=True)

    Returns:
        API key string or None if not found/provided
    """
    from .llm import get_api_key_for_provider, get_preferred_provider, PROVIDERS

    # Check preferred provider first
    preferred = get_preferred_provider()
    if preferred:
        api_key = get_api_key_for_provider(preferred)
        if api_key:
            return api_key

    # Check all providers
    for provider in PROVIDERS:
        api_key = get_api_key_for_provider(provider)
        if api_key:
            return api_key

    # Prompt user if allowed
    if prompt_if_missing:
        return prompt_for_api_key()

    return None


def prompt_for_api_key(provider: str = None) -> Optional[str]:
    """
    Interactively prompt user for API key and offer to save it.

    Args:
        provider: Specific provider to configure. If None, user chooses.

    Returns:
        API key string or None if user declines
    """
    from .llm import PROVIDERS

    print("\n" + "=" * 60)
    print("LLM API Key Setup")
    print("=" * 60)

    # Let user choose provider if not specified
    if not provider:
        print("\nSherpa supports multiple LLM providers:")
        providers_list = list(PROVIDERS.keys())
        for i, p in enumerate(providers_list, 1):
            info = PROVIDERS[p]
            print(f"  {i}. {info['display_name']}")

        print()
        try:
            choice = input(f"Choose provider [1-{len(providers_list)}] (default: 1): ").strip()
            if not choice:
                choice = "1"
            idx = int(choice) - 1
            if 0 <= idx < len(providers_list):
                provider = providers_list[idx]
            else:
                print("Invalid choice.")
                return None
        except (ValueError, KeyboardInterrupt):
            print("\nCancelled.")
            return None

    info = PROVIDERS[provider]
    print(f"\n{info['display_name']} selected.")
    print(f"Get your API key at: {info['url']}")
    print("\nYour key will be stored locally in ~/.sherpa/config.json")
    print("(This file is private and never shared or committed)")
    print()

    try:
        api_key = getpass("Paste your API key (input hidden): ").strip()

        if not api_key:
            print("\nNo key provided. Some features will be disabled.")
            return None

        # Validate format (basic check)
        expected_prefix = info['key_prefix']
        if not api_key.startswith(expected_prefix):
            print(f"\nWarning: Key doesn't look like a {provider} key (expected prefix: '{expected_prefix}')")
            confirm = input("Save anyway? [y/N]: ").strip().lower()
            if confirm != 'y':
                return None

        # Offer to save
        save = input("\nSave key to ~/.sherpa/config.json for future sessions? [Y/n]: ").strip().lower()

        if save != 'n':
            config = load_config()
            config[info['config_key']] = api_key
            config['preferred_provider'] = provider
            save_config(config)
            print(f"Key saved! {info['display_name']} set as preferred provider.")
        else:
            print("Key will only be used for this session.")

        return api_key

    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return None


def clear_api_key(provider: str = None) -> None:
    """Remove stored API key from config"""
    from .llm import PROVIDERS

    config = load_config()

    if provider:
        # Clear specific provider
        if provider in PROVIDERS:
            key = PROVIDERS[provider]['config_key']
            if key in config:
                del config[key]
                save_config(config)
                print(f"{provider} API key removed from config.")
            else:
                print(f"No stored {provider} API key found.")
    else:
        # Clear all API keys
        removed = []
        for p, info in PROVIDERS.items():
            if info['config_key'] in config:
                del config[info['config_key']]
                removed.append(p)

        if removed:
            save_config(config)
            print(f"Removed API keys for: {', '.join(removed)}")
        else:
            print("No stored API keys found.")


def get_config_value(key: str, default: Any = None) -> Any:
    """Get a specific config value"""
    config = load_config()
    return config.get(key, default)


def set_config_value(key: str, value: Any) -> None:
    """Set a specific config value"""
    config = load_config()
    config[key] = value
    save_config(config)
