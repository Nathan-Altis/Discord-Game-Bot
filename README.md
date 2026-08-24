# Culling Game Master Bot

**Culling Game Master Bot** is a Discord-based game management bot built in Python. It was designed to support a competitive player-driven challenge system inspired by elimination-style games, where players register, wager points, complete challenges, report winners, vote on rule changes, and risk elimination through inactivity or point loss.

This project is currently in **Beta v0.1.0** and is being actively tested and improved.

## Project Overview

The purpose of this bot is to automate the core systems needed to run a Discord-based competitive game community. Instead of manually tracking points, disputes, challenges, and player status, the bot manages the game state through slash commands and a SQLite database.

Players can challenge one another, wager points, confirm match results, propose rule changes, and appear on a live leaderboard. Admins have additional tools to resolve disputes, adjust points, manage players, and oversee the game.

## Current Features

- Player registration system
- Starting point balance for new players
- Public leaderboard
- Player point tracking
- Available and locked point tracking
- Player challenge system
- Point wagering between players
- Challenge acceptance and decline commands
- Automatic expiration of pending challenges after 7 days
- Winner reporting system
- Match confirmation by both players
- Dispute detection when players report different winners
- Admin dispute resolution
- Admin point adjustment tools
- Admin player management tools
- Rule proposal system
- Player and admin rule approval process
- Inactivity penalty system
- Automatic elimination when a player reaches 0 points
- SQLite database storage
- Render deployment support
- Keep-alive web server support for uptime monitoring

## Tech Stack

- **Python**
- **discord.py**
- **SQLite**
- **Render**
- **UptimeRobot**
- **Flask keep-alive web server**
- **python-dotenv** for environment variables

## How the Game Works

Each player registers through the Discord bot and starts with a set number of points. Players can challenge each other by selecting a game, opponent, and wager amount.

When a challenge is accepted, the wagered points are locked from both players. After the match, both players must report the winner. If both players report the same winner, the bot automatically transfers the points. If the reports do not match, the challenge becomes disputed and requires admin review.

Players who lose all points are marked as eliminated.

## Inactivity System

The bot includes an automatic inactivity penalty system. Inactivity is currently based on point activity, not general Discord chat activity.

If a player goes 7 days without a valid point change, the bot applies a penalty. The penalty increases with each inactive streak:

- First inactivity penalty: 25 points
- Second inactivity penalty: 50 points
- Third inactivity penalty: 75 points
- Penalties continue increasing by 25 points per inactive streak

If the penalty reduces a player to 0 points, the player is automatically eliminated.

## Rule Proposal System

Players can spend points to propose a rule change. A rule proposal requires:

- 1 admin approval
- 3 active player approvals

Player rejection votes are tracked, but they do not block a rule from passing. An admin rejection can fail a rule proposal.

## Admin Tools

Admins have access to commands that allow them to:

- Add or restore players
- Remove players
- Eliminate players
- Add, remove, or set player points
- Resolve disputed matches
- Fail rule proposals
- Monitor and manage the game state

## Deployment

The bot is currently hosted on Render using the free web service tier. Because Render free services may spin down due to inactivity, a keep-alive web server is included and an UptimeRobot monitor is used to ping the Render URL every five minutes.

This helps reduce downtime, but uptime may still vary while hosted on a free service.

## Current Known Issue

### Render Free-Tier Hosting Limitation

The bot is currently deployed as a Render free web service instead of a paid always-on background worker. Because of this, the bot may occasionally disconnect or restart if the service becomes inactive.

### Current Workaround

An UptimeRobot monitor is configured to ping the Render service every five minutes. This workaround is being monitored for stability during beta testing.

## Planned Improvements

Future updates may include:

- More detailed player profile stats
- Better activity tracking
- Admin dashboard or web panel
- Improved logging
- Match history command
- Challenge history command
- Automated announcement messages
- More advanced rule voting options
- Persistent cloud database support
- Improved deployment setup using a background worker or paid hosting tier

## Project Status

**Current Version:** Beta v0.1.0  
**Status:** Active development / live beta testing

This project is being developed as both a functional Discord game bot and a portfolio project to demonstrate practical experience with Python, Discord bot development, database design, automation, deployment, and user-focused feature planning.

## What I Learned

This project helped me practice:

- Building a Discord bot with slash commands
- Creating and managing a SQLite database
- Designing game logic and player state systems
- Handling edge cases such as disputes, inactivity, and elimination
- Deploying a Python application to Render
- Using environment variables for secure bot token management
- Troubleshooting uptime and hosting limitations
- Writing maintainable backend logic for a real user community

## Disclaimer

This bot is currently in beta. Features, rules, and balance settings may change as testing continues.
