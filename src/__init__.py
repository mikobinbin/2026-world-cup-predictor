"""
World Cup Predictor — 世界杯冠军预测系统
"""

__version__ = "0.1.0"
__author__ = "Miko & Hermes"

from .models.player_scoring import Player, Squad, build_squad_from_data
from .models.team_scoring import TeamScorer, TeamResult, score_all_teams
from .models.mystic_factor import MysticFactorEngine, generate_mystic_report
from .simulation.monte_carlo import MonteCarloSimulator, run_full_simulation
