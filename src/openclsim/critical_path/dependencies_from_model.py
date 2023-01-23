"""
Module contains DependenciesFromModel that inherits from critical_path.base_cp.BaseCP

in original commit this module would contain may lines and many (hidden/protected)
helper functions and methods which ar enot all listed here
"""
import networkx as nx

from openclsim.critical_path.base_cp import BaseCP


class DependenciesFromModel(BaseCP):
    """Build dependecies from recorded_activities_df"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_dependency_list(self):
        """
        Get dependencies from simulation setup and
        cross reference with recorded activities to get dependencies of relevant instances
        requires self.object_list, self.activity_list and self.recorded_activities_df

        Notes
        ---------
        this method is likely to provide too few dependencies and might raise warnings
        for unsupported start event conditions, activities et cetera

        this method contains approx 1000 (!) lines in original commit

        Returns
        -------
        dependency_list : list of tuples
            like [(A1, A2), (A1, A3), (A3, A4)] where A2 depends on A1 (A1 'causes' A2) et cetera
        """

        # get dependencies from DependencyGraph - so at model setup level (not time based yet)
        my_graph = DependencyGraph(self.activity_list)
        dependencies_act = my_graph.getListDependencies()

        # also get dependencies from start events - HAS LIMITATIONS
        dependencies_start = get_act_dependencies_start(self.activity_list)

        # convert these dependencies to depencies of the activity 'instances',
        # i.e. dependencies within the simulation/with time component
        cp_dependencies = get_dependencies_time(
            self.recorded_activities_df, dependencies_act + dependencies_start
        )

        # get cp dependencies based on resource utilisation vs capacity - HAS LIMITATIONS
        cp_depencies_res_limitation = get_resource_capacity_dependencies(
            self.recorded_activities_df, self.object_list
        )

        # get cp dependencies 'WAIT' - HAS LIMITATIONS
        cp_dependencies_wait = get_wait_dependencies_cp(self.recorded_activities_df)

        return list(
            set(cp_dependencies + cp_depencies_res_limitation + cp_dependencies_wait)
        )


# Waiting related start events
def get_wait_dependencies_cp(recorded_activities_df):
    """
    Get/assume dependencies between activities related to waiting. Waiting
    activities must explicitly be marked in the CpLog object as ``WAITING``.

    Parameters
    -----------
    recorded_activities_df : pd.DataFrame
        attribute of base_cp.BaseCP

    Returns
    --------
    list_wait_dependencies : list
        list of tuples of dependencies as occured in simulation
        (tuple of cp_activity_id) wrt WAITing

    .. warning::
        The definition of ``WAITING`` is up for discussion, as well as when and
        whether waiting is part of the critical path in the first place.

    .. warning::
        This function is preliminary, and hence has its limitations. Mostly due
        to critical information for dependencies in the way OpenCLSim now logs
        its information. For proper dependency checks for extracting the
        critical path, the logging module of OpenCLSim must be extended.

    """
    return []


def get_resource_capacity_dependencies(recorded_activities_df, objects_list):
    """
    Given a ``CpLog`` instance, and a list of OpenCLSim model objects this
    function inspects dependencies between activities which seen to be due to
    resource limitations.

    For all objects it checks the number of resources that are available. Then
    in the log it keeps track of the number of activities that occur at this
    object, assuming that these activities request a resource from the object.
    Hence, assumptions can be made on how many resources have been in use at a
    particular moment in the simulation. As a result, resource limitation
    dependencies between activities can be registered.

    Parameters
    ------------
    recorded_activities_df : pd.DataFrame
        attribute of base_cp.BaseCP
    objects_list : list
        list of all simulation objects (after simulation, e.g.
        [vessel, site, etc])

    .. warning::
        This function has some known limitations:
        - This function utilizes the logging and simulation objects after
          simulation. From this information it turns out that the actual
          resource request cannot be tracked down. Hence, it is assumed that
          if an activity takes place at an object, that also a resource is
          requested. This is not by default the case, examples can be created
          where an activity takes place at a simulation object without needing
          a resource request.

    Returns
    --------
    dependencies_list : list
        list of tuples of dependencies as occured in simulation
        (tuple of cp_activity_id) wrt resource capacity
    """
    return []


# Get dependencies based on start events
def get_act_dependencies_start(activities_list):
    """
    Get activity dependencies based on start event conditions.
    For now only 'container' type supported for base activities.

    Parameters
    ------------
    activities_list : list
        recorded main activity or list of main activities (after simulation)

    Returns
    ----------
    dependencies_start_act_list : list
        list of dependencies (tuples with activity ids)

    .. warning::
        Start events are currently only detected based on level-related start
        events. Hence, this function does not capture all start events!

    """
    return []


def get_dependencies_time(recorded_activities_df, dependencies_model_list):
    """
    Based on the model-based dependencies check these dependencies as they appear in the
    recorded_activities_df after simulation and convert/create depencies at simulation/time level

    Parameters
    -----------------
    recorded_activities_df : pd.DataFrame
        attribute of base_cp.BaseCP
    dependencies_model_list : list
        list of tuples of all (activity ID) dependencies

    Returns
    ---------
    dependencies_list : list
        list of tuples of dependencies as occured in simulation (tuple of cp_activity_id)

    """
    return []


class DependencyGraph:
    """
    Object used to capture top level dependencies in the model structure.

    This class can be used to generate a graph-based approach in detecting
    logical dependencies between OpenCLSim activities as extracted from the
    list of mail model activities. A directed graph is created where basic
    activities are represented by nodes, and their logical dependencies are
    the connecting directed graphs.

    For example, if a model setup contains a sequential activity
    ``A -> B -> C``, then the graph would show nodes ``A``, ``B`` and ``C`` for
    the activities, and the connecting edges ``(A, B)`` and ``(B, C)``.

    Parameters
    ----------
    main_activities : list
        The list of top level activities from the model setup. That is, if the
        model is set up with a WHILE activity on top level, then the list
        should only contain this WHILE activity, no matter the activities that
        are contained in it.
    """

    def __init__(self, main_activities):
        """Init."""
        # initiate
        self._main_activities = main_activities
        self.G = nx.DiGraph()

        # construct the graph
        self._constructGraph()

    def _constructGraph(self):
        """
        Construct the graph by drilling down from the top level activity all
        the way to the underlying base activities. Every time a node is created
        for an activity, and if it is not a basic activity, it is replaces by
        a sub-graph.

        For example, if we have a WHILE activity ``W``, containing a SEQUENTIAL
        activity ``S`` of the base activities ``A``, then ``B``, then ``C``,
        the graph would be built up in the following steps:

        1. Create single node ``W``, without edges.
        2. The ``W`` activity contains the sub-activity ``S``, hence replace
           node ``W`` by ``S``, and due to ``W`` being a while activity, add
           the edge ``(S, S)`` to the graph.
        3. Now, ``S`` contains the sequence ``A -> B -> C``, and must hence be
           replaced by the corresponding subgraph with nodes ``A``, ``B`` and
           ``C``, and the edges ``(A, B)`` and ``(B, C)``. By replacing ``S``,
           the resulting graph will have nodes ``A``, ``B`` and ``C``, edges
           ``(A, B)`` and ``(B, C)``, and also the edge ``(C, A)`` providing
           the recurrency from the while loop.
        4. Now all activities are base activities, hence this is the final
           form of the graph.

        """

    def getListDependencies(self):
        """Return the list of dependencies based on the graph."""
        return list(self.G.edges)

    def getListBaseActivities(self):
        """Return a list of the IDs of all base activities."""
        return list(self.G.nodes)
