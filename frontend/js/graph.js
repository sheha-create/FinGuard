class GraphVisualization {
    constructor(containerId) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.svg = null;
        this.simulation = null;
        this.nodes = [];
        this.links = [];
        this.width = 800;
        this.height = 600;
        this.initialized = false;

        this.waitForContainer();
    }

    waitForContainer() {
        const check = () => {
            if (this.container && this.container.clientWidth > 0 && this.container.clientHeight > 0) {
                this.init();
            } else {
                setTimeout(check, 100);
            }
        };
        check();
    }

    init() {
        this.width = this.container.clientWidth || 800;
        this.height = this.container.clientHeight || 600;

        this.svg = d3.select(`#${this.containerId}`)
            .append('svg')
            .attr('width', '100%')
            .attr('height', '100%');

        this.svg.append('defs').selectAll('marker')
            .data(['arrow'])
            .enter().append('marker')
            .attr('id', d => d)
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 25)
            .attr('refY', 0)
            .attr('markerWidth', 6)
            .attr('markerHeight', 6)
            .attr('orient', 'auto')
            .append('path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', '#666');

        this.g = this.svg.append('g');

        this.zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                this.g.attr('transform', event.transform);
            });

        this.svg.call(this.zoom);

        this.simulation = d3.forceSimulation()
            .force('link', d3.forceLink().id(d => d.id).distance(120))
            .force('charge', d3.forceManyBody().strength(-400))
            .force('center', d3.forceCenter(this.width / 2, this.height / 2))
            .force('collision', d3.forceCollide().radius(40));

        this.initialized = true;
        window.addEventListener('resize', () => this.handleResize());
    }

    handleResize() {
        if (!this.container) return;
        this.width = this.container.clientWidth || 800;
        this.height = this.container.clientHeight || 600;
        this.svg.attr('viewBox', `0 0 ${this.width} ${this.height}`);
        if (this.simulation) {
            this.simulation.force('center', d3.forceCenter(this.width / 2, this.height / 2));
            this.simulation.alpha(0.3).restart();
        }
    }

    update(graphData) {
        if (!this.initialized) return;

        this.nodes = graphData.nodes || [];
        this.links = graphData.edges || [];

        this.g.selectAll('*').remove();

        if (this.nodes.length === 0) return;

        this.simulation.nodes(this.nodes);
        this.simulation.force('link').links(this.links);

        const link = this.g.append('g')
            .attr('class', 'links')
            .selectAll('line')
            .data(this.links)
            .enter().append('line')
            .attr('class', d => `link ${d.risk_score > 0.6 ? 'flagged' : ''}`)
            .attr('stroke', d => this.getLinkColor(d.risk_score))
            .attr('stroke-width', d => Math.max(1, d.risk_score * 4))
            .attr('marker-end', 'url(#arrow)');

        const node = this.g.append('g')
            .attr('class', 'nodes')
            .selectAll('g')
            .data(this.nodes)
            .enter().append('g')
            .attr('class', 'node')
            .call(d3.drag()
                .on('start', (event, d) => this.dragStarted(event, d))
                .on('drag', (event, d) => this.dragged(event, d))
                .on('end', (event, d) => this.dragEnded(event, d)));

        node.append('circle')
            .attr('r', d => d.is_center ? 20 : 12)
            .attr('fill', d => this.getNodeColor(d))
            .attr('stroke', d => this.getNodeStroke(d))
            .attr('stroke-width', 2);

        node.append('text')
            .attr('dy', d => d.is_center ? 35 : 25)
            .attr('text-anchor', 'middle')
            .text(d => d.id.substring(0, 12));

        node.append('title')
            .text(d => `Account: ${d.id}\nOut: ${d.out_degree}\nIn: ${d.in_degree}`);

        link.append('title')
            .text(d => `Amount: $${d.amount.toFixed(2)}\nRisk: ${(d.risk_score * 100).toFixed(1)}%`);

        this.simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            node.attr('transform', d => `translate(${d.x},${d.y})`);
        });

        this.simulation.alpha(1).restart();

        this.fitGraph();
    }

    fitGraph() {
        if (this.nodes.length === 0) return;

        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;

        this.nodes.forEach(n => {
            if (n.x < minX) minX = n.x;
            if (n.x > maxX) maxX = n.x;
            if (n.y < minY) minY = n.y;
            if (n.y > maxY) maxY = n.y;
        });

        const padding = 80;
        const graphWidth = maxX - minX + padding * 2;
        const graphHeight = maxY - minY + padding * 2;

        const scale = Math.min(
            this.width / graphWidth,
            this.height / graphHeight,
            2
        ) * 0.8;

        const centerX = (minX + maxX) / 2;
        const centerY = (minY + maxY) / 2;

        const transform = d3.zoomIdentity
            .translate(this.width / 2, this.height / 2)
            .scale(scale)
            .translate(-centerX, -centerY);

        this.svg.transition()
            .duration(500)
            .call(this.zoom.transform, transform);
    }

    getLinkColor(riskScore) {
        if (riskScore > 0.8) return '#ef4444';
        if (riskScore > 0.6) return '#f59e0b';
        if (riskScore > 0.4) return '#3b82f6';
        return '#6b7280';
    }

    getNodeColor(node) {
        if (node.is_center) return '#3b82f6';
        if (node.out_degree > 5 || node.in_degree > 5) return '#f59e0b';
        return '#10b981';
    }

    getNodeStroke(node) {
        if (node.is_center) return '#60a5fa';
        return '#374151';
    }

    dragStarted(event, d) {
        if (!event.active) this.simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }

    dragEnded(event, d) {
        if (!event.active) this.simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }

    highlightNode(nodeId) {
        this.g.selectAll('.node')
            .classed('highlighted', d => d.id === nodeId);

        this.g.selectAll('.link')
            .classed('highlighted', d =>
                d.source.id === nodeId || d.target.id === nodeId);
    }

    clearHighlight() {
        this.g.selectAll('.node').classed('highlighted', false);
        this.g.selectAll('.link').classed('highlighted', false);
    }

    zoomToNode(nodeId) {
        const node = this.nodes.find(n => n.id === nodeId);
        if (node && node.x !== undefined) {
            const scale = 1.5;
            const x = this.width / 2 - node.x * scale;
            const y = this.height / 2 - node.y * scale;

            this.svg.transition()
                .duration(750)
                .call(this.zoom.transform,
                    d3.zoomIdentity.translate(x, y).scale(scale));
        }
    }
}

window.GraphVisualization = GraphVisualization;
