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
    Get the Anthropic API key from various sources.

    Priority:
    1. Environment variable ANTHROPIC_API_KEY
    2. Config file ~/.sherpa/config.json
    3. Interactive prompt (if prompt_if_missing=True)

    Returns:
        API key string or None if not found/provided
    """
    # 1. Check environment variable
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if api_key:
        return api_key

    # 2. Check config file
    config = load_config()
    api_key = config.get('anthropic_api_key')
    if api_key:
        return api_key

    # 3. Prompt user if allowed
    if prompt_if_missing:
        return prompt_for_api_key()

    return None


def prompt_for_api_key() -> Optional[str]:
    """
    Interactively prompt user for API key and offer to save it.

    Returns:
        API key string or None if user declines
    """
    print("\n" + "=" * 60)
    print("Anthropic API Key Required")
    print("=" * 60)
    print("\nSherpa needs an Anthropic API key for AI-powered features.")
    print("Get one at: https://console.anthropic.com/settings/keys")
    print("\nYour key will be stored locally in ~/.sherpa/config.json")
    print("(This file is private and never shared or committed)")
    print()

    try:
        api_key = getpass("Paste your API key (input hidden): ").strip()

        if not api_key:
            print("\nNo key provided. Some features will be disabled.")
            return None

        # Validate format (basic check)
        if not api_key.startswith('sk-ant-'):
            print("\nWarning: Key doesn't look like an Anthropic key (should start with 'sk-ant-')")
            confirm = input("Save anyway? [y/N]: ").strip().lower()
            if confirm != 'y':
                return None

        # Offer to save
        save = input("\nSave key to ~/.sherpa/config.json for future sessions? [Y/n]: ").strip().lower()

        if save != 'n':
            config = load_config()
            config['anthropic_api_key'] = api_key
            save_config(config)
            print("Key saved successfully!")
        else:
            print("Key will only be used for this session.")

        return api_key

    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return None


def clear_api_key() -> None:
    """Remove stored API key from config"""
    config = load_config()
    if 'anthropic_api_key' in config:
        del config['anthropic_api_key']
        save_config(config)
        print("API key removed from config.")
    else:
        print("No stored API key found.")


def get_config_value(key: str, default: Any = None) -> Any:
    """Get a specific config value"""
    config = load_config()
    return config.get(key, default)


def set_config_value(key: str, value: Any) -> None:
    """Set a specific config value"""
    config = load_config()
    config[key] = value
    save_config(config)
