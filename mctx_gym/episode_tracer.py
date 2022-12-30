"""
    MIT License

    Copyright (c) 2020 Microsoft Corporation.
    Copyright (c) 2021 github.com/coax-dev

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE
"""    

from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass
from collections import deque 
from itertools import islice
from jax import numpy as jnp

from .utils import sliceable_deque


@dataclass
class Transition:
    obs: Any
    a: int
    r: float
    done: bool
    Rn: float
    v: float
    pi: Any
    w: float = 1
    

class BaseTracer(ABC):

    @abstractmethod
    def reset(self):
        r"""
        Reset the cache to the initial state.
        """
        pass

    @abstractmethod
    def add(self, obs, a, r, done, v=0.0, pi=0.0, w=1.0):
        r"""
        Add a transition to the experience cache.
        Parameters
        ----------
        obs : state observation
            A single state observation.
        a : action
            A single action.
        r : float
            A single observed reward.
        done : bool
            Whether the episode has finished.
        v : search tree root node value.
        pi : float, optional
            The action weights.
        w : float, optional
            Sample weight associated with the given state-action pair.
        """
        pass

    @abstractmethod
    def pop(self):
        r"""
        Pop a single transition from the cache.
        Returns
        -------
        transition : 
            
        """
        pass


class NStep(BaseTracer):
    r"""
    A short-term cache for :math:`n`-step bootstrapping.

    Parameters
    ----------
    n : positive int

        The number of steps over which to bootstrap.

    gamma : float between 0 and 1

        The amount by which to discount future rewards.

    record_extra_info : bool, optional
    """

    def __init__(self, n, gamma, record_extra_info=False):
        self.n = int(n)
        self.gamma = float(gamma)
        self.record_extra_info = record_extra_info
        self.reset()

    def reset(self):
        self._deque_s = sliceable_deque([])
        self._deque_r = sliceable_deque([])
        self._done = False
        self._gammas = jnp.power(self.gamma, jnp.arange(self.n))
        self._gamman = jnp.power(self.gamma, self.n)

    def add(self, obs, a, r, done, v=0.0, pi=0.0, w=1.0):
        # if self._done and len(self):
        #     raise EpisodeDoneError(
        #         "please flush cache (or repeatedly call popleft) before appending new transitions")

        self._deque_s.append((obs, a, v, pi, w))
        self._deque_r.append(r)
        self._done = bool(done)

    def __len__(self):
        return len(self._deque_s)

    def __bool__(self):
        return bool(len(self)) and (self._done or len(self) > self.n)

    def pop(self):
        # if not self:
        #     raise InsufficientCacheError(
        #         "cache needs to receive more transitions before it can be popped from")

        # pop state-action (propensities) pair
        obs, a, v, pi, w = self._deque_s.popleft()

        # n-step partial return
        Rn = jnp.sum(self._gammas * jnp.array(self._deque_r[:self.n])).item()
        r = self._deque_r.popleft()

        # keep in mind that we've already popped 
        if len(self) >= self.n:
            obs_next, a_next, v_next, pi_next, _ = self._deque_s[self.n - 1]
            done = False
        else:
            # no more bootstrapping
            obs_next, a_next, v_next, pi_next, done = obs, a, v, pi, True
        
        Rn += v_next * self._gamman

        return Transition(obs=obs, a=a, r=r, done=done, Rn=Rn, v=v, pi=pi, w=w)
