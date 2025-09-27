"""
Command parser for Telegram bot commands with improved structure and validation.
"""


class CommandParser:
    def __init__(self, bot_username=None, debug=False):
        self.bot_username = bot_username
        self.debug = debug
        # Command registry mapping command aliases to (requires_params, validation_func)
        self.commands = {
            # Summary commands
            's': (False, None),
            'summ': (False, None),
            'summary': (False, None),
            'generate': (False, None),
            'tldr': (False, None),
            
            # Show commands
            'show': (False, None),
            'l': (False, None),
            'last': (False, None),
            
            # Status command
            'status': (False, None),
            
            # Help commands
            '?': (False, None),
            'help': (False, None),
            
            # Parameter commands
            'tier': (True, self._validate_tier),
            'pay': (True, self._validate_amount),
            'buy': (True, self._validate_amount),
            'p': (True, self._validate_amount),
        }
        
        # Command aliases to primary names
        self.aliases = {
            's': 'summary',
            'summ': 'summary',
            'generate': 'summary',
            'tldr': 'summary',
            'l': 'show',
            'last': 'show',
            '?': 'help',
            'buy': 'pay',
            'p': 'pay',
        }

    def parse(self, text):
        """
        Parse command text and return ParseResult.
        Only processes commands that end with the bot username.
        
        Returns:
            ParseResult with command, params, and validation status
        """
        if not text or not text.startswith('/'):
            return ParseResult(is_command=False)
        
        # Remove leading slash
        command_text = text[1:].strip()
        if not command_text:
            return ParseResult(is_command=False)
        
        # Split into command and parameters
        parts = command_text.split(' ', 1)
        full_command = parts[0].lower()
        params = parts[1].strip() if len(parts) > 1 else ''
        
        # Check if command ends with bot username - if not, treat as regular message
        if not full_command.endswith(self.bot_username.lower()):
            return ParseResult(is_command=False)
        
        # Remove bot username from command to get actual command
        command = full_command[:-len(self.bot_username)]
        
        # Check if command exists
        if command not in self.commands:
            return ParseResult(
                is_command=True,
                command=command,
                params=params,
                is_valid=False,
                error="Unknown command"
            )
        
        requires_params, validator = self.commands[command]
        
        # Check if required parameters are missing
        if requires_params and not params:
            return ParseResult(
                is_command=True,
                command=command,
                params=params,
                is_valid=False,
                error=f"Command /{command} requires parameters"
            )
        
        # Validate parameters if validator exists
        if validator and params:
            is_valid, error = validator(params, self.debug)
            if not is_valid:
                return ParseResult(
                    is_command=True,
                    command=command,
                    params=params,
                    is_valid=False,
                    error=error
                )
        
        # Get primary command name
        primary_command = self.aliases.get(command, command)
        
        return ParseResult(
            is_command=True,
            command=primary_command,
            params=params,
            is_valid=True
        )

    def _validate_tier(self, params, debug=False):
        """Validate tier command parameters"""
        tier_names = {"free", "basic", "plus", "pro", "max", "elite"}
        if params.lower() not in tier_names:
            return False, "Invalid tier. Choose from: free, basic, plus, pro, max, elite"
        return True, None

    def _validate_amount(self, params, debug=False):
        """Validate payment amount parameters"""
        try:
            amount = int(params)
        except ValueError:
            return False, "Invalid amount! Please specify a number between 50-5000"

        if debug:
            return True, None
        
        if amount < 50 or amount > 5000:
            return False, "Invalid amount! Please specify between 50-5000 stars"
            
        return True, None


class ParseResult:
    """Result of command parsing"""
    
    def __init__(self, is_command=False, command=None, params='', is_valid=True, error=None):
        self.is_command = is_command
        self.command = command
        self.params = params
        self.is_valid = is_valid
        self.error = error
    
    def __bool__(self):
        return self.is_command and self.is_valid